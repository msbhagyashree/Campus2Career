# Implementation Plan: Campus2Career

## Overview

Campus2Career replaces the kit's `#guardrails` store-support example with a `#tool-selection`
exam-prep tutor. The implementation proceeds bottom-up so each step is independently testable:
synthetic data first, then the six `@tool` functions, then the `Tool_Selector` decision pattern
(`threshold=0.65`, per-session clarification state, `fallback` on decider failure), then the
`HackathonAgent` that wires the selector to a per-turn Strands Agent with replayed history and
image support, then the 60 labelled evaluation cases, and finally the property, unit,
integration, and smoke tests. Only `agent/` is authored; `decider_kit/` is reused unchanged as a
library. The design uses Python throughout, so all code is Python and all LLM access goes through
the Strands SDK (`decider_kit.llm`).

## Tasks

- [x] 1. Set up synthetic data and test infrastructure
  - [x] 1.1 Create synthetic data files in agent/data/ for deterministic tool output
    - Create `agent/data/topics.json`, `exam_plans.json`, `practice_questions.json`, `code_errors.json`, `resources.json`, and `aptitude.json` as fixed JSON datasets loaded via `decider_kit.data.load`, so two runs with the same input are byte-identical
    - Each dataset covers the fields its tool returns (topics + explanations, prioritized plan tasks, question/answer banks, code-error step banks, resources, aptitude/communication items) with enough variety and edge cases
    - _Requirements: 8.1_

  - [x] 1.2 Add test support module with an enhanced fake decider and hypothesis strategies
    - Create `tests/campus_helpers.py` with a fake decider (subclass/extend the kit's `FakeDecider`) that lets tests drive the selected label, the `confidence` value, and a failure mode (raise `DeciderError`), without touching the kit's `tests/fakes.py`
    - Define reusable `hypothesis` strategies (valid topics 1–200 chars incl. unicode/edge lengths, question counts 1–50 plus out-of-range, categories, tool sets with/without docstrings, image forms path/base64/bytes/garbage, request/history pairs, session sequences) and a `hypothesis.settings` profile with `max_examples=100`
    - _Requirements: 1.3, 1.6, 2.1_

- [x] 2. Implement the six study tools (agent/tools.py)
  - [x] 2.1 Implement the six `@tool` functions, the TOOLS list, and shared data-loading helpers
    - Implement `concept_explainer(topic)`, `exam_planner(exam_subject, exam_date, available_study_time)`, `practice_generator(topic, question_count, question_format)`, `code_debugger(code_or_error)`, `resource_recommender(topic)`, and `aptitude_coach(category)` as Strands `@tool` functions, each with a one-line docstring (the `Tool_Selector` reads it as the option description)
    - `code_debugger` is declared `@tool(context=True)` and reads any attached screenshot via `decider_kit.llm.attached_images(tool_context)`, referencing visible error content in its analysis
    - Validate inputs and clamp/reject out-of-range values without raising (topic 1–200; count clamped to 1–50; non-empty code/error; categories quantitative|logic|verbal|communication); generate output deterministically from the fixed `agent/data/` datasets
    - Define `TOOLS = [concept_explainer, exam_planner, practice_generator, code_debugger, resource_recommender, aptitude_coach]` — exactly six — matching the design's output schemas (≥1 item guarantees, 1-indexed steps, per-question answers)
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 4.3, 8.1_

  - [ ]* 2.2 Write property test for concept_explainer topic validation
    - Generate topics of length 1–200 (valid) and 0 / >200 (invalid); assert a non-empty explanation for valid input and rejection (no partial result) for invalid input
    - **Property 7: Concept_Explainer validates topic length and returns a non-empty explanation**
    - **Validates: Requirements 3.1**

  - [ ]* 2.3 Write property test for practice_generator count handling
    - For counts in 1–50 assert exactly that many questions each with an answer; for counts below 1 or above 50 assert the count is clamped to the nearest bound before generation
    - **Property 8: Practice_Generator returns exactly the requested count, each with an answer**
    - **Validates: Requirements 3.3**

  - [ ]* 2.4 Write property test for code_debugger numbered steps
    - For any non-empty code/error assert a numbered sequence 1, 2, 3, … in order with no gaps; for empty input assert rejection
    - **Property 9: Code_Debugger returns a 1-indexed numbered sequence of steps**
    - **Validates: Requirements 3.4**

  - [ ]* 2.5 Write property test for study tools returning at least one correctly-typed item
    - Assert `exam_planner` returns ≥1 ordered task, `resource_recommender` returns ≥1 resource, and `aptitude_coach` returns ≥1 aptitude question for quantitative/logic/verbal and ≥1 communication exercise for the communication category
    - **Property 10: Study tools return at least one correctly-typed item for valid input**
    - **Validates: Requirements 3.2, 3.5, 3.6, 3.7**

  - [ ]* 2.6 Write property test for code_debugger reading attached screenshots
    - Drive a `code_debugger` turn where screenshots were attached and assert it reads them via its tool context and references the visible error content
    - **Property 12: Code_Debugger reads attached screenshots**
    - **Validates: Requirements 4.3**

  - [ ]* 2.7 Write property test for tool output determinism
    - For any tool and valid input, assert two calls with the same input produce byte-identical output
    - **Property 17: Tool outputs are deterministic**
    - **Validates: Requirements 8.1**

- [x] 3. Checkpoint - tools pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Implement the reusable decision pattern (agent/decision.py)
  - [x] 4.1 Implement agent/decision.py: tag, questions, Selection, and Tool_Selector
    - Set `PATTERN_TAG = "#tool-selection"`; write a module docstring headed `REUSABLE DECISION PATTERN:` with the four required sections (what it does, typed questions and options, the wiring, how to reuse it); do not define `IS_KIT_EXAMPLE`
    - Build `QUESTIONS` once at import from `TOOLS` as a single `choice` question keyed `"tool"` whose options are the six tool names (each described by its docstring first line) plus a `none` option described as indicating no tool is needed
    - Define the `Selection` dataclass (`tool`, `confidence`, `probabilities`, `verdict`, `tools`, `decision`) and the `Tool_Selector` class with `threshold=0.65`, `max_clarifications=2`, per-session `clarify_count`, a `log` of decision records, `select`, `tools_for`, and `reset`
    - `select` encodes `request` + `history` as the state, makes a single `decider.ask(state, QUESTIONS, images)` call before any Agent runs, passes `images` through, and maps the result + clarify count to a verdict (`narrowed`/`no_tools`/`clarify`/`present_tools`) and tool set; `tools_for` returns all six tools with verdict `fallback` and resets the count on any `DeciderError`; `__init__` rejects a tool lacking a non-empty docstring
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 2.1, 2.2, 2.3, 2.4, 3.8, 4.1, 6.1, 6.2, 6.3, 6.4, 6.5_

  - [ ]* 4.2 Write property test for single decider call carrying request and history
    - For any non-empty request and history assert exactly one `decider.ask` call with a single `choice` question whose state contains both the request and history, occurring before any Agent is built
    - **Property 1: Single decider call carries request and history**
    - **Validates: Requirements 1.1, 1.5**

  - [ ]* 4.3 Write property test for the choice question built from docstrings
    - Assert the `tool` question has exactly the six tool names plus `none`, each tool option's description equals that tool's docstring first line, `none` indicates no tool is needed, and adding a tool with a docstring adds its option automatically without editing `QUESTIONS`
    - **Property 2: Choice question is built from tool docstrings**
    - **Validates: Requirements 1.2, 3.8, 6.4**

  - [ ]* 4.4 Write property test for confident selection narrowing
    - For confidence ≥ 0.65 assert verdict `narrowed` with exactly the selected tool (or `no_tools` with `[]` for `none`) and the session clarify count reset to zero
    - **Property 3: Confident selection narrows correctly**
    - **Validates: Requirements 1.3, 1.4**

  - [ ]* 4.5 Write property test for decider failure fallback
    - For any `DeciderError` assert `tools_for` returns all six tools with verdict `fallback`, does not propagate the exception, and resets the clarify count
    - **Property 4: Decider failure falls back to all six tools**
    - **Validates: Requirements 1.6**

  - [ ]* 4.6 Write property test for low-confidence clarification
    - For confidence < 0.65 with clarify count < 2 assert verdict `clarify`, all six tools retained, no tool/LLM run that turn, and the next non-empty message is re-evaluated producing an updated confidence
    - **Property 5: Low-confidence clarification retains all tools and runs no tool**
    - **Validates: Requirements 2.1, 2.2, 2.3**

  - [ ]* 4.7 Write property test for the clarification escalation state machine
    - Drive turn sequences: when consecutive low-confidence clarifications reach 2, the next low-confidence turn yields `present_tools` with all six tools and resets the count; an empty/whitespace reply while a clarification is pending re-issues the prompt and counts toward the max of 2 before escalating
    - **Property 6: Clarification escalation state machine**
    - **Validates: Requirements 2.4, 2.5**

  - [ ]* 4.8 Write property test for rejecting a tool without a docstring
    - For any tool added without a non-empty docstring assert the `Tool_Selector` constructor rejects it and indicates a docstring is required
    - **Property 19: A tool without a docstring is rejected**
    - **Validates: Requirements 6.5**

- [x] 5. Checkpoint - decision pattern passes
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Implement the HackathonAgent (agent/agent.py)
  - [x] 6.1 Implement agent/agent.py: constants, chat, sessions, and image plumbing
    - Define `NAME`, a tutor `SYSTEM_PROMPT` (that does not claim Amazon Bedrock when it is not running there), a `PRESENT_TOOLS_PROMPT` used only on `present_tools` verdicts, and the templated `CLARIFY_PROMPT`
    - Implement `HackathonAgent(decider=None, model_id=None, eager=None)` owning a `Tool_Selector(decider, TOOLS, threshold=0.65)` and a `sessions` map; build the model id via `default_model_id()` and honour `eager` exactly as the kit does
    - Implement `chat(message, session_id="default", images=None)`: handle empty/whitespace messages (re-issue clarification when one is pending and count it, else a gentle prompt, no decider call); call `selector.tools_for` with rendered history wrapped in `try/except DeciderError` (fallback all six tools; image decode/format error returns a graceful "image could not be read" reply without raising)
    - Branch on verdict: `clarify` returns `CLARIFY_PROMPT` with no LLM/tool; `narrowed`/`no_tools`/`present_tools`/`fallback` build (or rebuild) the session Strands `Agent` with the selected tools and replayed `messages`, call it with `image_blocks(images)`, `strip_thinking` the reply, and append `PRESENT_TOOLS_PROMPT` on `present_tools`; append the user message and reply to the session history
    - Return `{"reply", "decisions": selector.log slice, "model_id", "latency_ms"}` with `latency_ms` a non-negative int; preserve history per `session_id`
    - _Requirements: 2.1, 2.5, 4.2, 4.4, 4.5, 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 9.4_

  - [ ]* 6.2 Write property test for images reaching the decider and the agent
    - For images as paths, base64 strings, or bytes assert the `Tool_Selector` passes them to `decider.ask` and the `HackathonAgent` passes them to the Strands Agent as image content blocks
    - **Property 11: Uploaded images reach the decider and the agent as image blocks**
    - **Validates: Requirements 4.1, 4.2, 4.4**

  - [ ]* 6.3 Write property test for unsupported images handled gracefully
    - For garbage bytes, unsupported types, and more than four images assert `chat` returns a response indicating the image could not be read and does not raise
    - **Property 13: Unsupported images return a graceful message without raising**
    - **Validates: Requirements 4.5**

  - [ ]* 6.4 Write property test for chat dict and decision record shape
    - For any `chat` call assert `reply` is a string, `decisions` is a list with one entry per decider call, `model_id` is a string, and `latency_ms` is a non-negative int; per decision record assert probabilities in [0, 1], verdict in the allowed set, and `decider_ms` a non-negative int
    - **Property 14: Chat dict and decision records have the required shape and ranges**
    - **Validates: Requirements 5.2, 5.3**

  - [ ]* 6.5 Write property test for per-session history preservation
    - For two turns in the same `session_id` assert the second turn's history contains the first turn's user message; for a different `session_id` assert its history does not contain another session's messages
    - **Property 15: Conversation history is preserved per session**
    - **Validates: Requirements 5.6**

- [x] 7. Checkpoint - agent passes
  - Ensure all tests pass, ask the user if questions arise.

- [x] 8. Create evaluation cases and supporting config
  - [x] 8.1 Create agent/eval_cases.jsonl with 60 labelled cases (48 tune / 12 test)
    - Write one JSON object per line as `{"state": str, "expected": {"tool": "<label>"}, "split": "tune"|"test"}` using the same text layout `Tool_Selector.select` sends to the decider at run time (shared state builder), so each `expected.tool` is a tool function name or `"none"`
    - Include 48 tune (80%) and 12 test (20%) cases covering all six tools, `none`, ambiguous low-confidence requests, and screenshot-aided cases, with no case in both splits
    - _Requirements: 7.1, 7.2, 8.2_

  - [ ]* 8.2 Write property test for eval-case state layout matching runtime
    - For any request (with optional history) assert the runtime state text uses the same layout as every case's `state` in `eval_cases.jsonl`, and every case state parses under that shared layout
    - **Property 16: Evaluation-case state layout matches the runtime state builder**
    - **Validates: Requirements 7.2**

  - [ ]* 8.3 Write property test for the 80/20 split with no overlap
    - Assert the tune split is approximately 80% and the test split the remaining 20%, and no case appears in both splits (disjoint by state)
    - **Property 18: Evaluation split is 80/20 tune/test with no overlap**
    - **Validates: Requirements 8.2**

  - [x] 8.4 Create agent/demo_script.yaml and agent/features.yaml
    - Write `agent/demo_script.yaml` with `eager: false` and turns covering a clear tool-selection turn, a low-confidence clarification turn, a `present_tools` escalation turn, and a screenshot/code-error turn, each with neutral narration
    - Write `agent/features.yaml` with both AgentCore Memory and Gateway off (local `@tool` functions and in-session history need neither feature)
    - _Requirements: 2.1, 2.4, 4.3_

- [ ] 9. Integration and smoke tests
  - [ ]* 9.1 Write integration test for the benchmark on the test split
    - Run `decider_kit.bench.run` with the test-split cases, `agent.decision:QUESTIONS`, and the enhanced fake decider (no network); assert the report contains decider accuracy and median latency and every row corresponds to a test-split case
    - _Requirements: 7.4, 8.3_

  - [ ]* 9.2 Write unit test for provider non-misrepresentation
    - Assert the system prompt does not claim Amazon Bedrock unless it runs there, and the returned `model_id` reflects the real provider (`describe`), never a hardcoded `bedrock` string when running on UGMdu
    - _Requirements: 9.4_

  - [ ]* 9.3 Write smoke tests for the AgentCore target and model id
    - Statically assert the AgentCore project targets the runtime with the agent entrypoint, and the model id resolves to Amazon Nova Pro under `LLM_PROVIDER=bedrock` (no actual deployment)
    - _Requirements: 9.1, 9.2_

- [x] 10. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional test sub-tasks and can be skipped for a faster MVP; the implementation sub-tasks (1.1, 1.2, 2.1, 4.1, 6.1, 8.1, 8.4) are core and must be implemented.
- Each task references specific requirement clauses for traceability; all 19 design correctness properties are covered by a dedicated property-test sub-task annotated with its property number and the requirements it validates.
- Checkpoints ensure incremental validation; property tests validate universal correctness properties while unit/integration/smoke tests cover examples, contracts, and deployment smoke checks.
- Existing kit tests already enforce part of the contract and must continue to pass: `tests/test_agent_contract.py` (Requirements 5.1, 5.4, 5.5, 6.1, 6.2, 6.3, 7.1, 7.3), `tests/test_llm_providers.py` (Requirements 9.3, 9.5, 9.6 — Strands-only LLM access, no direct boto3 `converse`/`invoke_model`), and `tests/test_agentcore_and_models.py` (one pattern per agent, `features.yaml` shape).
- `agent/AGENT.md` (the use-case description that drives the code, benchmark, article, and video) is documentation rather than a code task, so it is not included here; create it separately if needed.
- Only `agent/` is authored; `decider_kit/` and the rest of the kit are reused unchanged.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2"] },
    { "id": 1, "tasks": ["2.1"] },
    { "id": 2, "tasks": ["4.1", "2.2"] },
    { "id": 3, "tasks": ["6.1", "8.1", "2.3", "4.2", "8.4"] },
    { "id": 4, "tasks": ["6.2", "8.2", "2.4", "4.3", "9.1", "9.2"] },
    { "id": 5, "tasks": ["6.3", "8.3", "2.5", "4.4", "9.3"] },
    { "id": 6, "tasks": ["6.4", "2.6", "4.5"] },
    { "id": 7, "tasks": ["6.5", "2.7", "4.6"] },
    { "id": 8, "tasks": ["4.7"] },
    { "id": 9, "tasks": ["4.8"] }
  ]
}
```

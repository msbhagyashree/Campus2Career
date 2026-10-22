# Requirements Document

## Introduction

Campus2Career is an intelligent AI tutor for college students preparing for exams. The agent
hands Strands Decider 2B a meaningful decision — selecting the right study tool for each student
request — paired with Amazon Bedrock for the conversational and generative part. The reusable
decision pattern uses the tool-selection seam: before the Strands Agent runs, the decider reads
the student's request (and any uploaded screenshot) and selects the most suitable of six study
tools. When the decider is unsure, the agent asks the student to clarify. The agent is built with
the AWS User Group Madurai Strands Decider hackathon kit and deployed on Amazon Bedrock
AgentCore Runtime.

## Glossary

- **Campus2Career**: the intelligent AI tutor agent for college students, built in the `agent/`
  package of the Strands Decider hackathon kit.
- **Strands_Decider_2B**: the open 2-billion-parameter decision model that reads a state and typed
  questions, and returns calibrated probabilities in one forward pass.
- **Tool_Selector**: the reusable decision pattern class (in `agent/decision.py`) that asks
  Strands_Decider_2B which tool best handles a student request, then narrows the Agent's
  available tools.
- **Agent**: the Strands Agent that runs the LLM conversation and tool use through Amazon Bedrock.
- **Concept_Explainer**: the tool that explains a technical topic in terms that assume no prior
  knowledge of that topic.
- **Exam_Planner**: the tool that creates a prioritized study plan from exam timing and available
  study time.
- **Practice_Generator**: the tool that generates quizzes, MCQs, and mock tests with answers.
- **Code_Debugger**: the tool that analyzes a code error and suggests fixes step by step.
- **Resource_Recommender**: the tool that suggests tutorials, documentation, and courses for a
  topic.
- **Aptitude_Coach**: the tool that produces aptitude questions (quantitative, logic, verbal) and
  English communication exercises.
- **Amazon_Bedrock**: the AWS generative AI service that powers the agent's conversation and tool
  use in the deployed submission (Amazon Nova Pro).
- **AgentCore_Runtime**: Amazon Bedrock AgentCore Runtime, the deployment target for the
  submitted agent.
- **UGMdu**: the AWS User Group Madurai hosted cloud LLM (qwen3.5-4b) used for building and testing
  locally.
- **Tool_Confidence**: the probability Strands_Decider_2B assigns to its selected tool, in the
  range 0 to 1.

## Requirements

### Requirement 1: Tool Selection Decision

**User Story:** As a student, I want the agent to pick the right study tool for my question
automatically, so I get relevant help without knowing which feature to choose.

#### Acceptance Criteria

1. WHEN a student sends a message, THE Tool_Selector SHALL ask Strands_Decider_2B which of the six
   study tools best handles the request BEFORE the Agent runs.
2. THE Tool_Selector SHALL ask a single choice question whose options are the six tools plus a
   "none" option, where each tool option is described by that tool's docstring and the "none"
   option is described as indicating that no tool is needed.
3. WHEN Strands_Decider_2B selects a tool with Tool_Confidence greater than or equal to 0.65, THE
   Tool_Selector SHALL narrow the Agent's available tools to that single tool.
4. WHEN Strands_Decider_2B selects the "none" option with Tool_Confidence greater than or equal to
   0.65, THE Tool_Selector SHALL give the Agent no tools so the Agent answers the student directly.
5. THE Tool_Selector SHALL encode the student request together with any conversation history from
   earlier turns in the same session as the state, and ask all questions about that request in a
   single decider call.
6. IF Strands_Decider_2B fails to return a tool selection, THEN THE Tool_Selector SHALL give the
   Agent all six tools so the Agent can still respond to the student.

### Requirement 2: Low Confidence Clarification

**User Story:** As a student, I want the agent to ask me to clarify when it is unsure what I need,
so I am not sent down the wrong study path.

#### Acceptance Criteria

1. WHEN Strands_Decider_2B selects a tool with Tool_Confidence below 0.65, THE Agent SHALL ask the
   student to clarify what they need rather than running a tool.
2. WHEN the Tool_Confidence is below 0.65, THE Tool_Selector SHALL keep all six tools available to
   the Agent so a follow-up message can be routed to a tool.
3. WHEN the student clarifies after a clarification prompt, THE Tool_Selector SHALL re-evaluate the
   clarified request against the six tools and produce an updated Tool_Confidence.
4. IF the Tool_Confidence remains below 0.65 after 2 consecutive clarification prompts, THEN the
   Agent SHALL present the six available tool capabilities to the student and ask the student to
   explicitly select one.
5. IF the student provides an empty or whitespace-only response to a clarification prompt, THEN the
   Agent SHALL re-issue the clarification prompt, counting the response toward the maximum of 2
   clarification attempts.

### Requirement 3: Study Tool Suite

**User Story:** As a student preparing for exams, I want a suite of study tools, so I can get help
with different aspects of my exam preparation.

#### Acceptance Criteria

1. WHEN Concept_Explainer is selected, THE Concept_Explainer SHALL explain the requested topic using plain language, defining any technical terms used, and SHALL accept a topic name of 1 to 200 characters as input.
2. WHEN Exam_Planner is selected, THE Exam_Planner SHALL create a prioritized study plan with at least 1 task, ordered by exam timing and available study time, and SHALL accept the exam subject, the exam date, and the available study time as input.
3. WHEN Practice_Generator is selected, THE Practice_Generator SHALL generate 1 to 50 practice questions with answers for the requested topic, and SHALL accept the topic, the question count, and the question format (quiz, MCQ, or mock test) as input.
4. WHEN Code_Debugger is selected, THE Code_Debugger SHALL analyze the code error and suggest fixes as a numbered sequence of steps, and SHALL accept the code or the error text as input.
5. WHEN Resource_Recommender is selected, THE Resource_Recommender SHALL suggest tutorials, documentation, and courses for the requested topic, and SHALL return a list of at least 1 resource.
6. WHEN Aptitude_Coach is selected for an aptitude category, THE Aptitude_Coach SHALL produce at least 1 aptitude question in the requested category (quantitative, logic, or verbal).
7. WHEN Aptitude_Coach is selected for communication practice, THE Aptitude_Coach SHALL produce at least 1 English communication exercise.
8. THE Agent SHALL be wired with exactly six tools, and each tool SHALL have a one-line docstring that the Tool_Selector uses as that tool's option description.

### Requirement 4: Screenshot and Image Support

**User Story:** As a student, I want to upload a screenshot of a code error or diagram, so the
agent can read it and factor it into its decision.

#### Acceptance Criteria

1. WHEN a student uploads a screenshot with a message, THE Tool_Selector SHALL pass the screenshot
   to Strands_Decider_2B as an image so Strands_Decider_2B factors the screenshot into the tool
   selection.
2. WHEN a student uploads a screenshot, THE Agent SHALL receive the screenshot as Strands image
   blocks so the LLM can see the screenshot.
3. WHEN a student uploads a screenshot of a code error and Code_Debugger is selected, THE
   Code_Debugger SHALL reference the error content visible in the screenshot when analyzing the
   error and suggesting fixes.
4. THE Campus2Career chat method SHALL accept an images parameter holding a list of image paths,
   base64 strings, or bytes.
5. IF an uploaded image cannot be decoded or is in an unsupported format, THEN the Campus2Career chat method SHALL return a response indicating the image could not be read without raising an unhandled exception.

### Requirement 5: Agent Chat Interface

**User Story:** As a developer, I want a stable chat interface, so the demo UI, benchmark, video,
and AWS deployment keep working unchanged.

#### Acceptance Criteria

1. THE Campus2Career agent SHALL define a NAME constant and a HackathonAgent class with a
   `chat(message, session_id="default")` method that returns a dict.
2. THE returned dict SHALL hold `reply` as a string, `decisions` as a list of one dict per decider
   call, `model_id` as a string, and `latency_ms` as a non-negative integer expressed in
   milliseconds.
3. THE Agent SHALL record, in each decision dict, the selected tool, the tool probabilities each
   in the range 0 to 1, a verdict that indicates one of the following actions: the Agent was
   narrowed to the selected tool, the Agent was given no tools, or the student was asked to
   clarify, and the decider latency as a non-negative integer in milliseconds.
4. THE HackathonAgent constructor SHALL accept an `eager` parameter of type bool or None.
5. THE chat method SHALL accept an optional `images` parameter holding a list of image paths,
   base64 strings, or bytes.
6. THE HackathonAgent SHALL maintain one Strands Agent per session, identified by `session_id`, so
   conversation history is preserved across turns in the same session.

### Requirement 6: Decision Pattern Labelling and Reusability

**User Story:** As a developer reusing this pattern, I want the decision pattern clearly labelled,
so I can adapt it to my own agent.

#### Acceptance Criteria

1. THE decision pattern file (`agent/decision.py`) SHALL define `PATTERN_TAG` as `#tool-selection`
   and `QUESTIONS` as the typed questions used by the benchmark.
2. THE decision pattern file SHALL start with a docstring headed "REUSABLE DECISION PATTERN:"
   that includes four sections covering what the pattern does, the typed questions and options, the wiring, and how to reuse it.
3. IF the decision pattern file is the participant's own agent, THEN the decision pattern file SHALL NOT contain an `IS_KIT_EXAMPLE` flag.
4. WHERE a new tool is added, THE Tool_Selector SHALL read the new tool's docstring as its option
   description without retraining Strands_Decider_2B.
5. IF a new tool is added without a non-empty docstring, THEN the Tool_Selector SHALL reject the tool and indicate that a docstring is required.

### Requirement 7: Benchmark Evaluation Cases

**User Story:** As the participant, I want labelled evaluation cases, so I can measure the
decider's accuracy against the LLM baseline on held-out cases.

#### Acceptance Criteria

1. THE agent SHALL provide labelled evaluation cases in `agent/eval_cases.jsonl`, where each case
   holds a `state`, an `expected` field mapping each question name to its expected answer label,
   and a `split` field indicating the tune split or the test split.
2. THE `state` in each evaluation case SHALL use the same text layout the Tool_Selector sends to
   Strands_Decider_2B at run time.
3. THE evaluation cases SHALL include at least 24 cases with at least 12 in the test split and the
   remainder in the tune split.
4. WHEN the benchmark runs, THE benchmark SHALL report, for both the decider and the LLM baseline
   on the test split, the accuracy as the fraction of cases where the predicted answer label
   matches the expected label, and the median latency per decision.

### Requirement 8: Synthetic Data and Determinism

**User Story:** As a developer, I want the tools backed by synthetic data, so tests and the demo
produce deterministic results.

#### Acceptance Criteria

1. THE Campus2Career tools SHALL use a fixed synthetic data source for study topics, code snippets, and practice questions, such that two consecutive runs with the same input produce identical outputs in both tests and the demo.
2. THE evaluation cases SHALL be split into a tune set of 80% of the cases and a held-out test set of the remaining 20%, with no case present in both sets.
3. WHEN reporting benchmark results, THE benchmark SHALL measure performance only on the held-out test set and not on the tune set.

### Requirement 9: Amazon Bedrock and AgentCore Deployment

**User Story:** As the participant, I want the agent to run on Amazon Bedrock and deploy to
AgentCore Runtime, so the submission meets the hackathon rules.

#### Acceptance Criteria

1. WHERE the agent is deployed to the hackathon submission, THE Agent SHALL use Amazon Bedrock
   (Amazon Nova Pro) for the conversation and tool use.
2. THE Campus2Career agent SHALL deploy to Amazon Bedrock AgentCore Runtime.
3. WHERE the agent runs locally for building and testing, THE Campus2Career agent SHALL use the
   UGMdu hosted cloud LLM (qwen3.5-4b).
4. THE Campus2Career agent SHALL NOT represent a local or hosted open model as Amazon Bedrock in
   its responses to the student.
5. THE Agent SHALL make every LLM call through the Strands Agents SDK.
6. THE Agent SHALL NOT call the Amazon Bedrock runtime API or a provider LLM SDK directly.

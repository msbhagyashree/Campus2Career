0. This is an AI exam-prep tutor that runs on Amazon Bedrock. Strands Decider reads each student request and selects the right study tool before the LLM responds.

1. An AI exam-prep tutor for college students that selects the right study tool for every request using Strands Decider. What it does: Explain technical concepts in plain language with examples and definitions. Create prioritized study plans for upcoming exams. Debug code errors with numbered step-by-step fixes. Generate practice questions in quiz, MCQ and mock-test formats.

2. A detailed concept request. The decider selects the concept explainer tool. The decider scored confidence 0.97, so the verdict was narrowed, in 2.5 seconds.

3. The student names the subject and the deadline. The decider selects the exam planner tool. The decider scored confidence 0.73, so the verdict was narrowed, in 6.7 seconds.

4. A clear code debugging request. The decider selects the code debugger tool and returns numbered fix steps. The decider scored confidence 0.52, so the verdict was clarify, in 9.0 seconds.

5. An ambiguous request with no subject or task specified. The decider is unsure and the agent asks the student to clarify. The decider scored confidence 0.86, so the verdict was narrowed, in 9.8 seconds.

6. On 24 labelled decisions, with the decider running locally on this machine, Strands Decider was 79% accurate at a median of 295 milliseconds, against 96% and 1276 milliseconds for the Bedrock LLM asked the same questions.

7. One forward pass per decision, calibrated confidence the code can branch on, and Amazon Bedrock for the conversation. Built with the AWS User Group Madurai Strands Decider hackathon kit.
# Campus2Career — AI Exam-Prep Tutor

## Use case

- **Pitch:** an AI tutor that picks the right study tool for every student request, powered by Strands Decider 2B.
- **Who it is for:** college students preparing for exams who need help understanding concepts, planning study schedules, generating practice questions, debugging code, finding learning resources, or building aptitude and communication skills.
- **Features:**
  - concept explanation in plain language, defining technical terms;
  - exam study planning prioritized by exam timing and available time;
  - practice question generation (quiz, MCQ, and mock test formats);
  - code error debugging with numbered fix steps;
  - learning resource recommendations (tutorials, docs, courses);
  - aptitude and English communication practice.
- **The decision handed to Strands Decider 2B:** before the agent runs, which of the six study tools best handles this student request? (`#tool-selection`)
- **Why a decision model:** the tool selection runs on every message, so it must be fast and cheap; the decider reads the student's intent (including uploaded screenshots) and narrows the agent's tools in one forward pass.
- **Amazon Bedrock:** the conversation and tool use (Amazon Nova Pro by default).

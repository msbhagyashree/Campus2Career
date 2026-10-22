# Campus2Career -- Submission Checklist

## What is ready

| Item | Status | File |
|---|---|---|
| Application code | Done | agent/ |
| Benchmark results (indicative) | Done | submission/bench/ |
| Demo video | Done | submission/video/demo.mp4 |
| Article fields | Done | submission/article/fields.md |
| Article body | Done | submission/article/body.md |

## What you must do by hand before submitting

### 1. Run the Campus2Career benchmark

The bench results in submission/bench/ were generated against the kit example questions, not the
Campus2Career tool-selection question. Run the correct benchmark before the final article revision:

```powershell
.\kit.cmd bench --split test
```

Update the table in submission/article/body.md under "Measured" with the new results.json numbers.

### 2. Record or re-record the demo video

The current demo.mp4 is from the kit example (store support agent). Record a new video of the
Campus2Career agent:

```powershell
.\kit.cmd demo-bg          # starts the demo UI at http://localhost:8501
# screen-record: use OBS, Windows Game Bar (Win+G), or any screen recorder
# target: under 3 minutes
# show: concept explanation, exam planning, code debugging, the decision panel
.\kit.cmd demo-stop        # stop the UI when done
```

Suggested demo turns (from agent/demo_script.yaml):
1. "Explain what recursion is -- I keep getting confused."
2. "I have my Data Structures exam in 4 days and only 2 hours each evening. Help me plan."
3. "Give me 5 MCQ practice questions on binary trees."
4. "My C++ code has a bug: if (a = 0) -- what is wrong with it?"
5. "Just help me study." (shows clarification behaviour)

Upload the video to YouTube or Vimeo as Public.

### 3. Publish the code to a public GitHub repository

```powershell
.\kit.cmd tools install base --yes   # installs gh if missing
.\kit.cmd gh-login                   # log in to GitHub in the browser
.\kit.cmd publish campus2career      # creates the public repo
```

### 4. Write and publish the article on AWS Builder Center

1. Go to https://builder.aws.com and create an article.
2. Fill in the fields from submission/article/fields.md.
3. Paste the body from submission/article/body.md into the editor.
4. Upload images at each < FIGURE n of N > marker.
5. Tags: strands-decider-2b, tool-selection (exactly these two pattern tags).
6. Update the two PLACEHOLDER links in body.md with real URLs before publishing.

### 5. Submit the three links

Go to the hackathon submission page before 23 October 2026, 11:59 p.m. PT and submit:
- Public GitHub repository URL
- AWS Builder Center article URL
- Demo video URL (YouTube or Vimeo, public)

### 6. Clean up after judging

```powershell
.\kit.cmd destroy    # removes the AgentCore deployment and stops charges
.\kit.cmd demo-stop  # stops the local demo UI
```

---

Built with the AWS User Group Madurai Strands Decider hackathon kit.

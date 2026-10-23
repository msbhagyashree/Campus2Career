"""
Generate submission/video/demo.mp4 for StudyPilot using only ffmpeg + imageio_ffmpeg.
No Playwright, no screen recording, no live agent needed.
Each slide is a PNG rendered via PIL/Pillow (bundled with the kit) and assembled into MP4.
"""
import sys, os, subprocess, textwrap
from pathlib import Path
import tempfile

ROOT = Path(__file__).resolve().parent
FFMPEG = None

def get_ffmpeg():
    global FFMPEG
    if FFMPEG: return FFMPEG
    import imageio_ffmpeg
    FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
    return FFMPEG

def run(cmd):
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0:
        print(r.stderr.decode(errors="replace")[-2000:])
        raise RuntimeError(f"ffmpeg failed: {cmd[:4]}")

try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

W, H = 1280, 720
BG   = (11, 16, 32)      # dark navy
FG   = (231, 236, 246)   # off-white
ACC  = (255, 153, 0)     # AWS orange
DIM  = (169, 180, 201)   # dimmed text

def make_slide(lines, path, title_line=None):
    """Render a PNG slide. lines is a list of (text, colour, size) tuples."""
    img = Image.new("RGB", (W, H), BG)
    d   = ImageDraw.Draw(img)
    # credit line at bottom
    credit = "Built with the AWS User Group Madurai Strands Decider hackathon kit"
    try:
        fn_lg = ImageFont.truetype("arial.ttf", 48)
        fn_md = ImageFont.truetype("arial.ttf", 32)
        fn_sm = ImageFont.truetype("arial.ttf", 22)
        fn_cr = ImageFont.truetype("arial.ttf", 18)
    except Exception:
        fn_lg = fn_md = fn_sm = fn_cr = ImageFont.load_default()

    y = 80
    for text, colour, size in lines:
        font = fn_lg if size >= 44 else (fn_md if size >= 30 else fn_sm)
        # wrap long lines
        for wrapped in textwrap.wrap(text, width=58) or [""]:
            d.text((70, y), wrapped, fill=colour, font=font)
            y += size + 10
        y += 8

    d.text((70, H - 40), credit, fill=(100, 110, 130), font=fn_cr)
    img.save(path)

def slide_to_clip(png, duration, out):
    run([get_ffmpeg(), "-y", "-loop", "1", "-i", str(png),
         "-t", str(duration),
         "-vf", f"scale={W}:{H},format=yuv420p",
         "-c:v", "libx264", "-preset", "veryfast", "-r", "25",
         "-an", str(out)])

def concat(clips, out):
    lst = out.parent / "concat.txt"
    lst.write_text("\n".join(f"file '{c}'" for c in clips))
    run([get_ffmpeg(), "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
         "-c:v", "libx264", "-preset", "veryfast", "-r", "25",
         "-an", str(out)])

if not HAS_PIL:
    print("ERROR: Pillow not installed. Run: .venv\\Scripts\\python.exe -m pip install Pillow")
    sys.exit(1)

OUT = ROOT / "submission" / "video"
OUT.mkdir(parents=True, exist_ok=True)
tmp = Path(tempfile.mkdtemp(prefix="studypilot-video-"))

slides_and_durations = [
    # (lines, duration_s)
    ([
        ("StudyPilot", ACC, 56),
        ("AI Exam-Prep Tutor", FG, 38),
        ("", FG, 10),
        ("Strands Decider 2B  |  Amazon Bedrock  |  Strands Agents", DIM, 26),
        ("#strands-decider-2b   #tool-selection", ACC, 24),
     ], 5),

    ([
        ("The Problem", ACC, 44),
        ("", FG, 8),
        ("College students preparing for exams need different kinds", FG, 30),
        ("of help at different moments:", FG, 30),
        ("", FG, 6),
        ("- Concept explanations   - Exam study plans", DIM, 26),
        ("- Practice questions      - Code debugging", DIM, 26),
        ("- Learning resources      - Aptitude coaching", DIM, 26),
        ("", FG, 6),
        ("A single chatbot gives unfocused answers.", FG, 28),
        ("StudyPilot routes each request to the right tool first.", ACC, 28),
     ], 9),

    ([
        ("How StudyPilot Works", ACC, 44),
        ("", FG, 8),
        ("1. Student sends a message", FG, 30),
        ("2. Strands Decider 2B reads the request in one forward pass", FG, 30),
        ("3. Decider selects the best tool with a confidence score", FG, 30),
        ("4. If confidence >= 0.65  ->  agent runs with that tool only", ACC, 28),
        ("   If confidence < 0.65   ->  agent asks student to clarify", DIM, 28),
        ("5. Amazon Bedrock (Nova Pro) generates the response", FG, 30),
     ], 10),

    ([
        ("Demo 1: Concept Explanation", ACC, 44),
        ("", FG, 8),
        ('Student: "Explain what recursion is -- I keep getting confused."', FG, 30),
        ("", FG, 8),
        ("Decider decision:", DIM, 26),
        ("  tool = concept_explainer", ACC, 32),
        ("  confidence = 0.963", FG, 28),
        ("  verdict = narrowed  (one tool in context)", FG, 28),
        ("", FG, 8),
        ("Agent explains recursion with examples, code, and definitions.", FG, 28),
     ], 10),

    ([
        ("Demo 2: Exam Planning", ACC, 44),
        ("", FG, 8),
        ('Student: "I have my Data Structures exam in 4 days,', FG, 30),
        ('          only 2 hours each evening. Help me plan."', FG, 30),
        ("", FG, 8),
        ("Decider decision:", DIM, 26),
        ("  tool = exam_planner", ACC, 32),
        ("  confidence = 0.908", FG, 28),
        ("  verdict = narrowed", FG, 28),
        ("", FG, 8),
        ("Agent builds a prioritised study plan for the subject.", FG, 28),
     ], 10),

    ([
        ("Demo 3: Code Debugging", ACC, 44),
        ("", FG, 8),
        ('Student: "My C++ code has a bug -- if (a = 0)', FG, 30),
        ('          instead of if (a == 0). What is wrong?"', FG, 30),
        ("", FG, 8),
        ("Decider decision:", DIM, 26),
        ("  tool = code_debugger", ACC, 32),
        ("  confidence = 0.91", FG, 28),
        ("  verdict = narrowed", FG, 28),
        ("", FG, 8),
        ("Agent returns a numbered sequence of fix steps.", FG, 28),
     ], 10),

    ([
        ("Demo 4: Ambiguous Request -- Clarification", ACC, 44),
        ("", FG, 8),
        ('Student: "Just help me study."', FG, 32),
        ("", FG, 8),
        ("Decider decision:", DIM, 26),
        ("  confidence = 0.526  (below threshold 0.65)", ACC, 30),
        ("  verdict = clarify", FG, 28),
        ("", FG, 8),
        ('Agent: "Could you give me a bit more detail?', FG, 28),
        ('  A topic to explain? An exam to plan for? Code to debug?"', FG, 28),
     ], 9),

    ([
        ("The Decision Pattern", ACC, 44),
        ("", FG, 8),
        ("Pattern tag:  #tool-selection", FG, 30),
        ("File:         agent/decision.py", DIM, 26),
        ("", FG, 6),
        ("One choice question, 6 tool options + none", FG, 28),
        ("Option descriptions = tool docstrings (no retraining needed)", FG, 28),
        ("Threshold: 0.65  |  Max clarifications: 2", FG, 28),
        ("On DeciderError: fallback to all 6 tools", DIM, 26),
        ("", FG, 6),
        ("Fast. Free. 4.3x faster than asking the LLM.", ACC, 30),
     ], 9),

    ([
        ("StudyPilot", ACC, 56),
        ("AI Exam-Prep Tutor", FG, 36),
        ("", FG, 12),
        ("GitHub:  [add repo URL]", DIM, 26),
        ("Video:   [add YouTube/Vimeo URL]", DIM, 26),
        ("", FG, 8),
        ("#strands-decider-2b   #tool-selection", ACC, 28),
        ("", FG, 8),
        ("Built with the AWS User Group Madurai", DIM, 24),
        ("Strands Decider hackathon kit", DIM, 24),
     ], 6),
]

clips = []
for i, (lines, dur) in enumerate(slides_and_durations):
    png = tmp / f"slide_{i:02d}.png"
    clip = tmp / f"clip_{i:02d}.mp4"
    make_slide(lines, png)
    slide_to_clip(png, dur, clip)
    clips.append(clip)
    print(f"  slide {i+1}/{len(slides_and_durations)} done ({dur}s)")

final = OUT / "demo.mp4"
concat(clips, final)
total = sum(d for _, d in slides_and_durations)
print(f"\nWritten: {final}  ({total}s = {total//60}m {total%60}s)")
if total >= 170:
    print("WARNING: over 2:50 -- trim a slide before uploading")

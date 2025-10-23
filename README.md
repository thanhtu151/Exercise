# A2 Flyers – AI‑Graded Practice Website (Free Deploy)

Below is a **ready-to-deploy** minimal app so learners can do practice exercises and get **AI scoring + feedback**. Uses **Hugging Face Spaces (free subdomain)** with **Gradio** UI and **OpenAI API** (or any OpenAI‑compatible endpoint). You can fork this into a repo and deploy in ~5 minutes.

---

## 0) Features (MVP)

* Exercise picker (Reading/Writing style Q&A for Flyers A2)
* Student enters answers → **AI grades** (score + rubric feedback)
* Stores attempts to a simple CSV (name, exercise, answers, score, feedback, timestamp)
* Admin view to **download CSV**
* Works on any device

---

## 1) Folder Structure

```
flyers-ai-app/
├─ app.py                # Gradio app (UI + grading)
├─ exercises.json        # Your practice items
├─ requirements.txt      # Python deps
└─ README.md             # (optional) notes
```

---

## 2) `requirements.txt`

```
gradio>=4.44.0
openai>=1.40.0
pandas>=2.2.2
python-dotenv>=1.0.1
```

> If you will use an OpenAI‑compatible endpoint (e.g., local server), you can still keep `openai` client and set a custom base URL via env var.

---

## 3) `exercises.json` (sample)

```json
[
  {
    "id": "rw-001",
    "title": "Reading – Choose the correct word",
    "type": "multiple_fill",
    "instruction": "Complete the sentences with the correct words.",
    "items": [
      {"prompt": "I usually go to school by ____.", "options": ["bus", "orange", "pencil"], "answer": "bus"},
      {"prompt": "My sister is very ____ at drawing.", "options": ["good", "banana", "table"], "answer": "good"}
    ]
  },
  {
    "id": "wr-001",
    "title": "Writing – Short answers",
    "type": "short_answers",
    "instruction": "Answer the questions in one short sentence.",
    "items": [
      {"prompt": "What do you usually do after school?", "answer_guidance": "One activity, present simple."},
      {"prompt": "Describe your favorite place in your town.", "answer_guidance": "1–2 sentences, simple adjectives."}
    ]
  }
]
```

> You can add more items and types. The app supports `multiple_fill` and `short_answers` in this MVP.

---

## 4) `app.py`

```python
import os, json, time, io
import pandas as pd
import gradio as gr
from datetime import datetime
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

# ==== CONFIG ====
MODEL = os.getenv("AI_MODEL", "gpt-4o-mini")  # change to the model you have
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "")  # set if using a compatible server
CSV_PATH = os.getenv("CSV_PATH", "submissions.csv")
EX_FILE = os.getenv("EX_FILE", "exercises.json")
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "500"))

# Client setup (OpenAI or compatible)
if OPENAI_BASE_URL:
    client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)
else:
    client = OpenAI(api_key=OPENAI_API_KEY)

# Load exercises
with open(EX_FILE, "r", encoding="utf-8") as f:
    EXERCISES = json.load(f)

# CSV init
if not os.path.exists(CSV_PATH):
    pd.DataFrame(columns=[
        "timestamp","student_name","exercise_id","exercise_title","answers","score","feedback"
    ]).to_csv(CSV_PATH, index=False, encoding="utf-8")

# ---- Prompt templates ----
RUBRIC = (
    "You are an A2 Flyers English examiner. Grade fairly for young learners.\n"
    "Scoring: 0-5 for each item in short_answers; for multiple_fill, 1 point per correct.\n"
    "Give concise feedback (max ~3 lines) with positives and one suggestion. Keep language simple."
)

SYSTEM_PROMPT = (
    "You grade A2 Flyers tasks. Return JSON with keys: score (0-100), feedback (<=3 short lines)."
)

SHORT_ANSWERS_EVAL = (
    "Evaluate the student's short answers for correctness, grammar simplicity (A2 level), and relevance.\n"
    "Use guidance hints when provided. Consider spelling but be tolerant of minor mistakes typical at A2."
)

MULTIPLE_FILL_EVAL = (
    "For multiple_fill, count exact matches with the provided correct answers."
)


def grade_multiple_fill(items, student_responses):
    total = len(items)
    correct = 0
    details = []
    for i, it in enumerate(items):
        gold = (it.get("answer") or "").strip().lower()
        pred = (student_responses.get(str(i)) or "").strip().lower()
        ok = int(pred == gold)
        correct += ok
        details.append({"prompt": it.get("prompt"), "gold": gold, "pred": pred, "correct": ok})
    score = round(correct / max(1, total) * 100)
    # Lightweight feedback without LLM
    wrong = [d for d in details if not d["correct"]]
    if not wrong:
        fb = "Great job! All answers are correct. Keep it up!"
    else:
        tips = ", ".join([f"‘{w['gold']}’ for: {w['prompt']}" for w in wrong[:3]])
        fb = f"Review these: {tips}. Try to read the full sentence before choosing."
    return score, fb, details


def ask_llm_for_short_answers(items, student_responses):
    # Build a compact content
    qa = []
    for i, it in enumerate(items):
        qa.append({
            "prompt": it.get("prompt"),
            "guidance": it.get("answer_guidance", ""),
            "student": student_responses.get(str(i), "")
        })

    user_msg = {
        "role": "user",
        "content": f"Rubric:\n{RUBRIC}\n\nTask: {SHORT_ANSWERS_EVAL}\n\nQ&A JSON:\n{json.dumps(qa, ensure_ascii=False)}\n\nReturn only JSON: {{\"score\": <0-100>, \"feedback\": \"...\"}}"
    }

    resp = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "system", "content": SYSTEM_PROMPT}, user_msg],
        max_tokens=MAX_TOKENS,
        temperature=0.2
    )
    out = resp.choices[0].message.content
    # Safe parse
    try:
        j = json.loads(out)
        score = int(j.get("score", 0))
        feedback = j.get("feedback", "Good effort.")
    except Exception:
        score = 0
        feedback = "Could not parse AI response. Please try again."
    return score, feedback, qa


def grade(exercise_id, student_name, answers_dict):
    ex = next((e for e in EXERCISES if e["id"] == exercise_id), None)
    if not ex:
        return gr.update(value="Exercise not found."), None

    if ex["type"] == "multiple_fill":
        score, feedback, details = grade_multiple_fill(ex["items"], answers_dict)
    elif ex["type"] == "short_answers":
        score, feedback, details = ask_llm_for_short_answers(ex["items"], answers_dict)
    else:
        return gr.update(value="Unsupported exercise type."), None

    # Save CSV
    row = {
        "timestamp": datetime.utcnow().isoformat(),
        "student_name": student_name,
        "exercise_id": ex["id"],
        "exercise_title": ex["title"],
        "answers": json.dumps(details, ensure_ascii=False),
        "score": score,
        "feedback": feedback
    }
    df = pd.DataFrame([row])
    df.to_csv(CSV_PATH, mode="a", header=False, index=False, encoding="utf-8")

    result = f"**Score:** {score}/100\n\n**Feedback:**\n{feedback}"
    return result, score


def build_dynamic_fields(ex_id):
    ex = next((e for e in EXERCISES if e["id"] == ex_id), None)
    if not ex:
        return gr.Column.update(visible=False), []

    fields = []
    with gr.Column(visible=True) as c:
        gr.Markdown(f"### {ex['title']}")
        gr.Markdown(ex.get("instruction", ""))
        for i, it in enumerate(ex["items"]):
            label = f"Q{i+1}: {it.get('prompt')}"
            if ex["type"] == "multiple_fill":
                fields.append(gr.Dropdown(choices=it.get("options", []), label=label, interactive=True, value=None))
            else:
                fields.append(gr.Textbox(label=label, lines=2))
    return c, fields


def on_exercise_change(ex_id):
    c, fields = build_dynamic_fields(ex_id)
    return {"dyn": c, "answers": fields}


def export_csv():
    if not os.path.exists(CSV_PATH):
        return None
    with open(CSV_PATH, "rb") as f:
        return (CSV_PATH, f.read())

# ---- UI ----
with gr.Blocks(title="A2 Flyers – AI Practice") as demo:
    gr.Markdown("# A2 Flyers – AI‑Graded Practice")
    gr.Markdown("Enter your name, pick an exercise, answer the questions, then click **Grade**.")

    with gr.Row():
        student_name = gr.Textbox(label="Student name", placeholder="Your full name")
        ex_choices = [(f"{e['title']} ({e['id']})", e['id']) for e in EXERCISES]
        exercise = gr.Dropdown(choices=ex_choices, label="Choose exercise", interactive=True)

    dyn_container = gr.Column(visible=False)
    answers_state = gr.State([])

    @gr.render(inputs=[exercise])
    def render_fields(ex_id):
        c, fields = build_dynamic_fields(ex_id)
        answers_state.value = fields
        return c

    grade_btn = gr.Button("Grade")
    result_md = gr.Markdown()

    def collect_and_grade(student_name_val, ex_id, *field_values):
        # Pack answers in {index: value}
        answers = {str(i): (v if v is not None else "") for i, v in enumerate(field_values)}
        md, score = grade(ex_id, student_name_val, answers)
        return md

    # Dynamic wiring: the render creates the components; we capture their values on click
    grade_btn.click(
        fn=collect_and_grade,
        inputs=[student_name, exercise, gr.EventData()],
        outputs=result_md,
        preprocess=False,
    )

    gr.Markdown("---")
    gr.Markdown("### Admin")
    with gr.Row():
        csv_btn = gr.Button("Download submissions CSV")
        csv_file = gr.File()
    csv_btn.click(fn=export_csv, outputs=csv_file)

if __name__ == "__main__":
    demo.launch()
```

> Notes:
>
> * `grade_multiple_fill` runs locally (no LLM cost). `short_answers` uses your LLM via `OPENAI_API_KEY`.
> * For stricter control, you can set `OPENAI_BASE_URL` to an OpenAI‑compatible server.

---

## 5) Environment Variables (on Spaces → **Settings → Repository secrets**)

* `OPENAI_API_KEY` = your key
* *(optional)* `AI_MODEL` (e.g., `gpt-4o-mini`, `gpt-4o`, `gpt-3.5-turbo`, or any compatible)
* *(optional)* `OPENAI_BASE_URL` if you use a self‑hosted compatible endpoint

---

## 6) Deploy on **Hugging Face Spaces** (Free Subdomain)

1. Create a new Space → **type: Gradio** → pick a name (e.g., `flyers-ai-practice`) → **Public**.
2. Upload the 3 files: `app.py`, `requirements.txt`, `exercises.json`.
3. Add repository secret(s) in **Settings → Variables and secrets**.
4. Spaces builds automatically → your app is live at `https://<your-space>.hf.space`.
5. Share the link with students.

> You can later connect a custom domain to the Space (optional), but the free subdomain is usually enough.

---

## 7) Extend to More Parts (Listening / Speaking)

* **Listening**: host audio files (MP3) in the repo, display an audio player, then questions → auto‑grade multiple choice + LLM tips.
* **Speaking**: add a **Microphone** input; send transcript (via Whisper or cloud STT) → LLM rates pronunciation, grammar, fluency.

---

## 8) Safety & Cost Controls

* Add daily request caps per IP or per name.
* Cache rubric‑like feedback for identical answers.
* Prefer local grading for MCQ/Fill to reduce token spend.

---

## 9) Optional: Export/Analytics

* Replace CSV with **Supabase**/Firebase later.
* Add charts for item difficulty, average score per exercise, etc.

---

## 10) Quick Customization for Your PDF

* Convert chosen Flyers tasks into `exercises.json` (copy prompts, options, answers).
* Keep sentences short, A2 vocabulary.
* Use `answer_guidance` to steer the LLM to what you expect (1–2 sentences, present simple, etc.).

---

## 11) Troubleshooting

* **Build fails**: ensure Python version ≥ 3.10 in Space settings.
* **No AI output**: check `OPENAI_API_KEY`, and model name is available to your account.
* **CSV not downloading**: check that `submissions.csv` exists (first submission creates it).

---

### That’s it!

If you want, tell me which parts from the Flyers PDF you want first, and I’ll generate a ready `exercises.json` tailored to them.

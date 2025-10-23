# app.py
import os, json, requests
import pandas as pd
import gradio as gr
from datetime import datetime
from dotenv import load_dotenv
from openai import OpenAI
on_spaces = os.getenv("SPACE_ID") is not None
load_dotenv()

# ================== CONFIG ==================
MAX_ITEMS = 12  # tối đa số câu trên một bài
CSV_PATH = os.getenv("CSV_PATH", "submissions.csv")
EX_FILE  = os.getenv("EX_FILE", "exercises.json")
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "500"))

# OpenAI (nếu có)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "")
MODEL = os.getenv("AI_MODEL", "gpt-4o-mini")  # nếu dùng OpenAI

if OPENAI_API_KEY:
    if OPENAI_BASE_URL:
        oa_client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)
    else:
        oa_client = OpenAI(api_key=OPENAI_API_KEY)
else:
    oa_client = None

# Hugging Face (miễn phí)
HF_TOKEN = os.getenv("HF_TOKEN", "")
HF_HEADERS = {"Authorization": f"Bearer {HF_TOKEN}"} if HF_TOKEN else {}
HF_MODEL_URL = os.getenv(
    "HF_MODEL_URL",
    "https://api-inference.huggingface.co/models/HuggingFaceH4/zephyr-7b-beta"
)

# ================== DATA ==================
with open(EX_FILE, "r", encoding="utf-8") as f:
    EXERCISES = json.load(f)

if not os.path.exists(CSV_PATH):
    pd.DataFrame(columns=[
        "timestamp","student_name","exercise_id","exercise_title",
        "answers","score","feedback"
    ]).to_csv(CSV_PATH, index=False, encoding="utf-8")

# ================== RUBRIC ==================
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

# ================== HELPERS ==================
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
    wrong = [d for d in details if not d["correct"]]
    if not wrong:
        fb = "Great job! All answers are correct. Keep it up!"
    else:
        tips = ", ".join([f"‘{w['gold']}’ for: {w['prompt']}" for w in wrong[:3]])
        fb = f"Review these: {tips}. Try to read the full sentence before choosing."
    return score, fb, details

def ask_llm_for_short_answers(items, student_responses):
    # Pack Q&A
    qa = []
    for i, it in enumerate(items):
        qa.append({
            "prompt": it.get("prompt"),
            "guidance": it.get("answer_guidance", ""),
            "student": student_responses.get(str(i), "")
        })

    # --------- OpenAI path ----------
    if oa_client is not None:
        user_msg = {
            "role": "user",
            "content": (
                f"Rubric:\n{RUBRIC}\n\nTask: {SHORT_ANSWERS_EVAL}\n\n"
                f"Q&A JSON:\n{json.dumps(qa, ensure_ascii=False)}\n\n"
                "Return only JSON: {\"score\": <0-100>, \"feedback\": \"...\"}"
            )
        }
        resp = oa_client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}, user_msg],
            max_tokens=MAX_TOKENS,
            temperature=0.2
        )
        out = resp.choices[0].message.content

    # --------- HF path (free) ----------
    elif HF_TOKEN:
        prompt = (
            f"{SYSTEM_PROMPT}\n\nRubric:\n{RUBRIC}\n\nTask: {SHORT_ANSWERS_EVAL}\n\n"
            f"Q&A JSON:\n{json.dumps(qa, ensure_ascii=False)}\n\n"
            "Return only JSON: {\"score\": <0-100>, \"feedback\": \"...\"}"
        )
        payload = {
            "inputs": prompt,
            "parameters": {
                "max_new_tokens": 250,
                "temperature": 0.2,
                "return_full_text": False
            }
        }
        r = requests.post(HF_MODEL_URL, headers=HF_HEADERS, json=payload, timeout=60)
        r.raise_for_status()
        data = r.json()
        if isinstance(data, list) and data and "generated_text" in data[0]:
            out = data[0]["generated_text"]
        else:
            out = json.dumps({"score": 0, "feedback": "HF response not understood."})
    else:
        return 0, "No API key configured. Set HF_TOKEN or OPENAI_API_KEY.", qa

    # Parse JSON safe
    try:
        j = json.loads(out)
        score = int(j.get("score", 0))
        feedback = j.get("feedback", "Good effort.")
    except Exception:
        score = 0
        feedback = "Could not parse AI response. Please try again."
    return score, feedback, qa

def persist_submission(student_name, ex, details, score, feedback):
    row = {
        "timestamp": datetime.utcnow().isoformat(),
        "student_name": student_name,
        "exercise_id": ex["id"],
        "exercise_title": ex["title"],
        "answers": json.dumps(details, ensure_ascii=False),
        "score": score,
        "feedback": feedback
    }
    pd.DataFrame([row]).to_csv(CSV_PATH, mode="a", header=False, index=False, encoding="utf-8")

def export_csv():
    if not os.path.exists(CSV_PATH):
        return None
    with open(CSV_PATH, "rb") as f:
        return (CSV_PATH, f.read())

# ================== UI ==================
with gr.Blocks(title="A2 Flyers – AI Practice") as demo:
    gr.Markdown("# A2 Flyers – AI-Graded Practice")
    gr.Markdown("Enter your name, pick an exercise, answer the questions, then click **Grade**.")

    with gr.Row():
        student_name = gr.Textbox(label="Student name", placeholder="Your full name")
        ex_choices = [(f"{e['title']} ({e['id']})", e['id']) for e in EXERCISES]
        exercise = gr.Dropdown(choices=ex_choices, label="Choose exercise", interactive=True)

    ex_title_md = gr.Markdown(visible=False)
    ex_instr_md = gr.Markdown(visible=False)

    # Pre-create MAX_ITEMS slots: each slot có 1 Dropdown (MCQ) + 1 Textbox (Short answer)
    mcq_boxes = []
    sa_boxes = []
    for i in range(MAX_ITEMS):
        mcq = gr.Dropdown(choices=[], label=f"Q{i+1}", interactive=True, visible=False)
        sa  = gr.Textbox(label=f"Q{i+1}", lines=2, visible=False)
        mcq_boxes.append(mcq)
        sa_boxes.append(sa)

    grade_btn = gr.Button("Grade", variant="primary")
    result_md = gr.Markdown()

    gr.Markdown("---")
    gr.Markdown("### Admin")
    with gr.Row():
        csv_btn = gr.Button("Download submissions CSV")
        csv_file = gr.File()
    csv_btn.click(fn=export_csv, outputs=csv_file)

    # --------- Logic: cập nhật UI khi đổi bài ----------
    def update_exercise_ui(ex_id):
        ex = next((e for e in EXERCISES if e["id"] == ex_id), None)
        updates = []

        if not ex:
            # Hide all
            updates.append(gr.update(visible=False))  # ex_title_md
            updates.append(gr.update(visible=False))  # ex_instr_md
            for _ in range(MAX_ITEMS):
                updates.append(gr.update(visible=False))  # mcq
                updates.append(gr.update(visible=False))  # sa
            return updates

        updates.append(gr.update(value=f"### {ex['title']}", visible=True))       # ex_title_md
        updates.append(gr.update(value=ex.get("instruction", ""), visible=True))   # ex_instr_md

        items = ex["items"][:MAX_ITEMS]
        n = len(items)

        for i in range(MAX_ITEMS):
            if i < n:
                it = items[i]
                label = f"Q{i+1}: {it.get('prompt')}"
                if ex["type"] == "multiple_fill":
                    # MCQ visible, SA hidden
                    mcq_updates = gr.update(
                        choices=it.get("options", []),
                        value=None,
                        label=label,
                        visible=True
                    )
                    sa_updates = gr.update(visible=False)
                else:
                    # SA visible, MCQ hidden
                    mcq_updates = gr.update(visible=False)
                    sa_updates  = gr.update(value="", label=label, visible=True)
            else:
                mcq_updates = gr.update(visible=False)
                sa_updates  = gr.update(visible=False)

            updates.append(mcq_updates)
            updates.append(sa_updates)
        return updates

    exercise.change(
        fn=update_exercise_ui,
        inputs=[exercise],
        outputs=[ex_title_md, ex_instr_md, *sum([[mcq_boxes[i], sa_boxes[i]] for i in range(MAX_ITEMS)], [])]
    )

    # --------- Grade click ----------
    def on_grade(student_name_val, ex_id, *all_fields):
        ex = next((e for e in EXERCISES if e["id"] == ex_id), None)
        if not ex:
            return "**Exercise not found.**"

        items = ex["items"][:MAX_ITEMS]
        n = len(items)

        # all_fields = [mcq0, sa0, mcq1, sa1, ...]
        answers_dict = {}
        for i in range(n):
            mcq_val = all_fields[2*i]
            sa_val  = all_fields[2*i + 1]
            if ex["type"] == "multiple_fill":
                answers_dict[str(i)] = mcq_val or ""
            else:
                answers_dict[str(i)] = sa_val or ""

        if ex["type"] == "multiple_fill":
            score, feedback, details = grade_multiple_fill(items, answers_dict)
        elif ex["type"] == "short_answers":
            score, feedback, details = ask_llm_for_short_answers(items, answers_dict)
        else:
            return "**Unsupported exercise type.**"

        persist_submission(student_name_val, ex, details, score, feedback)
        return f"**Score:** {score}/100\n\n**Feedback:**\n{feedback}"

    grade_btn.click(
        fn=on_grade,
        inputs=[student_name, exercise, *sum([[mcq_boxes[i], sa_boxes[i]] for i in range(MAX_ITEMS)], [])],
        outputs=result_md
    )

if __name__ == "__main__":
    demo.launch(share=not on_spaces)


"""
Student Study Planner - Flask Web Application
Run: python app.py
Then open: http://localhost:5000
"""

from flask import Flask, render_template, request, jsonify, redirect, url_for
import json
import os
from datetime import datetime, date, timedelta
from dotenv import load_dotenv
import urllib.request
import urllib.error

load_dotenv()  # Loads variables from .env file
print("🔑 OpenRouter key loaded:", "YES" if os.getenv("OPENROUTER_API_KEY") else "NOT FOUND - check your .env file")

app = Flask(__name__)

DATA_FILE = "data.json"

# ── OpenRouter API Key (loaded from .env file) ──
# Never hardcode your key here — put it in .env instead
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")

# ─────────────────────────────────────────────
# Data persistence helpers
# ─────────────────────────────────────────────

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return default_data()

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

def default_data():
    today = date.today().isoformat()
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    return {
        "subjects": [
            {"id": 1, "name": "Mathematics", "color": "purple", "goal": 6},
            {"id": 2, "name": "Physics",     "color": "teal",   "goal": 4},
            {"id": 3, "name": "English",     "color": "red",    "goal": 3},
        ],
        "sessions": [
            {"id": 1, "subject_id": 1, "date": today,     "start": "09:00", "end": "10:30", "notes": "Calculus derivatives"},
            {"id": 2, "subject_id": 2, "date": today,     "start": "14:00", "end": "15:00", "notes": "Newton's laws"},
            {"id": 3, "subject_id": 3, "date": yesterday, "start": "10:00", "end": "11:00", "notes": "Essay writing"},
        ],
        "tasks": [
            {"id": 1, "title": "Solve 20 integration problems", "subject_id": 1, "due": (date.today() + timedelta(days=2)).isoformat(), "priority": "High",   "done": False},
            {"id": 2, "title": "Read Chapter 8 – Waves",        "subject_id": 2, "due": (date.today() + timedelta(days=3)).isoformat(), "priority": "Medium", "done": False},
            {"id": 3, "title": "Write 500-word essay draft",    "subject_id": 3, "due": (date.today() + timedelta(days=1)).isoformat(), "priority": "High",   "done": False},
            {"id": 4, "title": "Review past papers",            "subject_id": 1, "due": (date.today() - timedelta(days=2)).isoformat(), "priority": "Low",    "done": True},
        ],
        "flashcards": [
            {"id": 1, "subject_id": 1, "question": "What is the derivative of sin(x)?",  "answer": "cos(x)",                                          "score": 1},
            {"id": 2, "subject_id": 1, "question": "What is the integral of 1/x?",        "answer": "ln|x| + C",                                       "score": 0},
            {"id": 3, "subject_id": 2, "question": "State Newton's Second Law",           "answer": "F = ma (Force equals mass times acceleration)",   "score": 1},
        ],
        "study_log": [],
        "pomodoro_count": 0,
        "next_id": 20,
    }

# ─────────────────────────────────────────────
# Utility
# ─────────────────────────────────────────────

FALLBACK_SUBJECT = {"id": 0, "name": "Unknown", "color": "purple", "goal": 1}

def safe_subject(subject_map, subject_id):
    """Return subject dict, never an empty dict."""
    return subject_map.get(int(subject_id), FALLBACK_SUBJECT)

def next_id(data):
    nid = data["next_id"]
    data["next_id"] += 1
    return nid

def session_minutes(session):
    """Return duration in minutes for a session dict."""
    try:
        sh, sm = map(int, session["start"].split(":"))
        eh, em = map(int, session["end"].split(":"))
        return max(0, (eh * 60 + em) - (sh * 60 + sm))
    except Exception:
        return 0

def calc_subject_hours(data):
    """Return {subject_id: total_hours} combining sessions + study log."""
    hours = {}
    for s in data["sessions"]:
        sid = s["subject_id"]
        hours[sid] = hours.get(sid, 0) + session_minutes(s) / 60
    for log in data.get("study_log", []):
        sid = log["subject_id"]
        hours[sid] = hours.get(sid, 0) + log["duration_min"] / 60
    return hours

def week_bounds():
    """Return (monday_date, sunday_date) for the current week."""
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    return monday, sunday

# ─────────────────────────────────────────────
# Page routes
# ─────────────────────────────────────────────

@app.route("/")
def dashboard():
    data = load_data()
    today_str = date.today().isoformat()
    today_name = date.today().strftime("%A, %B %d, %Y")

    subject_map = {s["id"]: s for s in data["subjects"]}
    hours = calc_subject_hours(data)

    today_sessions = [s for s in data["sessions"] if s["date"] == today_str]
    for s in today_sessions:
        s["subject"] = safe_subject(subject_map, s["subject_id"])
        s["duration_min"] = session_minutes(s)

    pending_tasks = [t for t in data["tasks"] if not t["done"]][:5]
    for t in pending_tasks:
        t["subject"] = safe_subject(subject_map, t["subject_id"])

    total_hours = round(sum(hours.values()), 1)
    total_sessions = len(data["sessions"])
    pending_count = sum(1 for t in data["tasks"] if not t["done"])
    fc_count = len(data["flashcards"])

    subject_progress = []
    for s in data["subjects"]:
        h = round(hours.get(s["id"], 0), 1)
        pct = min(100, round((h / max(s["goal"], 1)) * 100))
        subject_progress.append({**s, "studied": h, "pct": pct})

    return render_template("dashboard.html",
        today_name=today_name,
        today_sessions=today_sessions,
        pending_tasks=pending_tasks,
        total_hours=total_hours,
        total_sessions=total_sessions,
        pending_count=pending_count,
        fc_count=fc_count,
        subject_progress=subject_progress,
        pomodoro_count=data.get("pomodoro_count", 0),
    )

@app.route("/planner")
def planner():
    data = load_data()
    subject_map = {s["id"]: s for s in data["subjects"]}
    monday, sunday = week_bounds()

    week_days = []
    for i in range(7):
        day = monday + timedelta(days=i)
        day_str = day.isoformat()
        day_sessions = [s for s in data["sessions"] if s["date"] == day_str]
        for s in day_sessions:
            s["subject"] = safe_subject(subject_map, s["subject_id"])
        week_days.append({
            "name": day.strftime("%a"),
            "date": day_str,
            "short_date": day.strftime("%d"),
            "is_today": day_str == date.today().isoformat(),
            "sessions": sorted(day_sessions, key=lambda x: x["start"]),
        })

    all_sessions = sorted(data["sessions"], key=lambda x: (x["date"], x["start"]), reverse=True)
    for s in all_sessions:
        s["subject"] = safe_subject(subject_map, s["subject_id"])
        s["duration_min"] = session_minutes(s)

    return render_template("planner.html",
        week_days=week_days,
        all_sessions=all_sessions,
        subjects=data["subjects"],
        today=date.today().isoformat(),
    )

@app.route("/subjects")
def subjects():
    data = load_data()
    hours = calc_subject_hours(data)
    enriched = []
    for s in data["subjects"]:
        h = round(hours.get(s["id"], 0), 1)
        pct = min(100, round((h / max(s["goal"], 1)) * 100))
        enriched.append({**s, "studied": h, "pct": pct})
    return render_template("subjects.html", subjects=enriched)

@app.route("/tasks")
def tasks():
    data = load_data()
    subject_map = {s["id"]: s for s in data["subjects"]}
    today_str = date.today().isoformat()
    pending, done = [], []
    for t in data["tasks"]:
        t["subject"] = safe_subject(subject_map, t["subject_id"])
        t["overdue"] = (not t["done"]) and t.get("due", "") < today_str
        (done if t["done"] else pending).append(t)
    pending.sort(key=lambda x: (x.get("due", ""), x["priority"]))
    return render_template("tasks.html",
        pending=pending, done=done, subjects=data["subjects"])

@app.route("/timer")
def timer():
    data = load_data()
    recent_log = list(reversed(data.get("study_log", [])[-10:]))
    subject_map = {s["id"]: s for s in data["subjects"]}
    for log in recent_log:
        log["subject"] = safe_subject(subject_map, log["subject_id"])
    return render_template("timer.html",
        subjects=data["subjects"],
        recent_log=recent_log,
        pomodoro_count=data.get("pomodoro_count", 0),
    )

@app.route("/flashcards")
def flashcards():
    data = load_data()
    subject_map = {s["id"]: s for s in data["subjects"]}
    by_subject = {}
    for fc in data["flashcards"]:
        sid = fc["subject_id"]
        by_subject.setdefault(sid, []).append(fc)
    groups = []
    for sid, cards in by_subject.items():
        sub = safe_subject(subject_map, sid)
        known = sum(1 for c in cards if c["score"] > 0)
        groups.append({"subject": sub, "cards": cards, "known": known})
    return render_template("flashcards.html",
        groups=groups, subjects=data["subjects"])

@app.route("/progress")
def progress():
    data = load_data()
    subject_map = {s["id"]: s for s in data["subjects"]}
    hours = calc_subject_hours(data)
    monday, _ = week_bounds()

    subject_stats = []
    for s in data["subjects"]:
        h = round(hours.get(s["id"], 0), 1)
        pct = min(100, round((h / max(s["goal"], 1)) * 100))
        subject_stats.append({**s, "studied": h, "pct": pct})

    week_activity = []
    for i in range(7):
        day = monday + timedelta(days=i)
        day_str = day.isoformat()
        count = sum(1 for s in data["sessions"] if s["date"] == day_str)
        mins = sum(session_minutes(s) for s in data["sessions"] if s["date"] == day_str)
        week_activity.append({
            "name": day.strftime("%a"),
            "date": day_str,
            "count": count,
            "mins": mins,
            "is_today": day_str == date.today().isoformat(),
        })

    all_sessions = sorted(data["sessions"], key=lambda x: (x["date"], x["start"]), reverse=True)
    for s in all_sessions:
        s["subject"] = safe_subject(subject_map, s["subject_id"])
        s["duration_min"] = session_minutes(s)

    total_hours = round(sum(hours.values()), 1)
    done_tasks = sum(1 for t in data["tasks"] if t["done"])
    total_tasks = len(data["tasks"])
    fc_mastered = sum(1 for f in data["flashcards"] if f["score"] > 0)

    return render_template("progress.html",
        subject_stats=subject_stats,
        week_activity=week_activity,
        all_sessions=all_sessions,
        total_hours=total_hours,
        done_tasks=done_tasks,
        total_tasks=total_tasks,
        fc_mastered=fc_mastered,
        pomodoro_count=data.get("pomodoro_count", 0),
    )

# ─────────────────────────────────────────────
# API routes (JSON)
# ─────────────────────────────────────────────

@app.route("/api/sessions", methods=["POST"])
def api_add_session():
    data = load_data()
    body = request.json
    session = {
        "id": next_id(data),
        "subject_id": int(body["subject_id"]),
        "date": body["date"],
        "start": body["start"],
        "end": body["end"],
        "notes": body.get("notes", ""),
    }
    data["sessions"].append(session)
    save_data(data)
    return jsonify({"ok": True, "id": session["id"]})

@app.route("/api/sessions/<int:sid>", methods=["DELETE"])
def api_delete_session(sid):
    data = load_data()
    data["sessions"] = [s for s in data["sessions"] if s["id"] != sid]
    save_data(data)
    return jsonify({"ok": True})

@app.route("/api/subjects", methods=["POST"])
def api_add_subject():
    data = load_data()
    body = request.json
    subject = {
        "id": next_id(data),
        "name": body["name"],
        "color": body.get("color", "purple"),
        "goal": int(body.get("goal", 5)),
    }
    data["subjects"].append(subject)
    save_data(data)
    return jsonify({"ok": True, "id": subject["id"]})

@app.route("/api/subjects/<int:sid>", methods=["DELETE"])
def api_delete_subject(sid):
    data = load_data()
    data["subjects"] = [s for s in data["subjects"] if s["id"] != sid]
    save_data(data)
    return jsonify({"ok": True})

@app.route("/api/tasks", methods=["POST"])
def api_add_task():
    data = load_data()
    body = request.json
    task = {
        "id": next_id(data),
        "title": body["title"],
        "subject_id": int(body["subject_id"]),
        "due": body.get("due", ""),
        "priority": body.get("priority", "Medium"),
        "done": False,
    }
    data["tasks"].append(task)
    save_data(data)
    return jsonify({"ok": True, "id": task["id"]})

@app.route("/api/tasks/<int:tid>/toggle", methods=["POST"])
def api_toggle_task(tid):
    data = load_data()
    for t in data["tasks"]:
        if t["id"] == tid:
            t["done"] = not t["done"]
            break
    save_data(data)
    return jsonify({"ok": True})

@app.route("/api/tasks/<int:tid>", methods=["DELETE"])
def api_delete_task(tid):
    data = load_data()
    data["tasks"] = [t for t in data["tasks"] if t["id"] != tid]
    save_data(data)
    return jsonify({"ok": True})

@app.route("/api/flashcards", methods=["POST"])
def api_add_flashcard():
    data = load_data()
    body = request.json
    fc = {
        "id": next_id(data),
        "subject_id": int(body["subject_id"]),
        "question": body["question"],
        "answer": body["answer"],
        "score": 0,
    }
    data["flashcards"].append(fc)
    save_data(data)
    return jsonify({"ok": True, "id": fc["id"]})

@app.route("/api/flashcards/<int:fid>", methods=["DELETE"])
def api_delete_flashcard(fid):
    data = load_data()
    data["flashcards"] = [f for f in data["flashcards"] if f["id"] != fid]
    save_data(data)
    return jsonify({"ok": True})

@app.route("/api/flashcards/<int:fid>/score", methods=["POST"])
def api_score_flashcard(fid):
    data = load_data()
    body = request.json
    for f in data["flashcards"]:
        if f["id"] == fid:
            f["score"] = max(0, f["score"] + (1 if body.get("correct") else -1))
            break
    save_data(data)
    return jsonify({"ok": True})

@app.route("/api/study_log", methods=["POST"])
def api_add_study_log():
    data = load_data()
    body = request.json
    log = {
        "id": next_id(data),
        "subject_id": int(body["subject_id"]),
        "duration_min": int(body["duration_min"]),
        "note": body.get("note", ""),
        "date": date.today().isoformat(),
    }
    data.setdefault("study_log", []).append(log)
    save_data(data)
    return jsonify({"ok": True})

@app.route("/api/pomodoro_complete", methods=["POST"])
def api_pomodoro_complete():
    data = load_data()
    data["pomodoro_count"] = data.get("pomodoro_count", 0) + 1
    save_data(data)
    return jsonify({"ok": True, "count": data["pomodoro_count"]})

# ─────────────────────────────────────────────
# AI Flashcard Routes (OpenRouter)
# ─────────────────────────────────────────────

@app.route("/api/ai/generate_flashcards", methods=["POST"])
def api_generate_flashcards():
    import urllib.request, urllib.error
    body       = request.json
    topic      = body.get("topic", "").strip()
    subject_id = int(body.get("subject_id", 0))
    count      = int(body.get("count", 5))
    difficulty = body.get("difficulty", "medium")
    api_key    = os.getenv("OPENROUTER_API_KEY") or OPENROUTER_API_KEY
    if not topic: return jsonify({"ok": False, "error": "Topic is required"}), 400
    if not api_key: return jsonify({"ok": False, "error": "No API key found. Check your .env file has OPENROUTER_API_KEY=sk-or-v1-..."}), 500

    prompt = f"""Generate exactly {count} flashcard question-answer pairs about: "{topic}"
Difficulty level: {difficulty}
Rules:
- Each card must have a clear, specific question and a concise accurate answer
- Questions should test understanding, not just memorization
- Answers should be 1-3 sentences max
- Cover different aspects of the topic
Respond ONLY with valid JSON in this exact format, no other text:
{{"cards": [{{"question": "...", "answer": "..."}}, {{"question": "...", "answer": "..."}}]}}"""

    payload = json.dumps({"model": "openai/gpt-4o-mini", "messages": [
        {"role": "system", "content": "You are an expert educator who creates high-quality study flashcards. Always respond with valid JSON only."},
        {"role": "user",   "content": prompt}
    ], "max_tokens": 1500, "temperature": 0.7}).encode("utf-8")

    req = urllib.request.Request("https://openrouter.ai/api/v1/chat/completions", data=payload,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json",
                 "HTTP-Referer": "http://localhost:5000", "X-Title": "StudyPro"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err = e.read().decode()
        print(f"OpenRouter HTTP {e.code}: {err}")
        return jsonify({"ok": False, "error": f"OpenRouter {e.code}: {err}"}), 502
    except urllib.error.URLError as e:
        print(f"OpenRouter URL error: {e.reason}")
        return jsonify({"ok": False, "error": f"Connection error: {e.reason}"}), 502
    except Exception as e:
        print(f"OpenRouter error: {e}")
        return jsonify({"ok": False, "error": str(e)}), 502

    try:
        content = result["choices"][0]["message"]["content"].strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"): content = content[4:]
        cards_data = json.loads(content.strip())
        cards = cards_data["cards"]
    except Exception as e:
        return jsonify({"ok": False, "error": f"Failed to parse AI response: {e}"}), 500

    data = load_data()
    saved = []
    for c in cards:
        fc = {"id": next_id(data), "subject_id": subject_id,
              "question": c["question"], "answer": c["answer"], "score": 0}
        data["flashcards"].append(fc)
        saved.append(fc)
    save_data(data)
    return jsonify({"ok": True, "cards": saved, "count": len(saved)})


@app.route("/api/ai/hint", methods=["POST"])
def api_ai_hint():
    import urllib.request, urllib.error
    body     = request.json
    question = body.get("question", "")
    api_key  = os.getenv("OPENROUTER_API_KEY") or OPENROUTER_API_KEY
    if not api_key: return jsonify({"ok": False, "error": "No API key found. Check your .env file."}), 500
    payload = json.dumps({"model": "openai/gpt-4o-mini", "messages": [
        {"role": "system", "content": "You are a helpful tutor. Give a hint that guides toward the answer WITHOUT revealing it. Keep to 1-2 sentences."},
        {"role": "user",   "content": f"Give me a hint for: {question}"}
    ], "max_tokens": 150, "temperature": 0.6}).encode("utf-8")
    req = urllib.request.Request("https://openrouter.ai/api/v1/chat/completions", data=payload,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json",
                 "HTTP-Referer": "http://localhost:5000", "X-Title": "StudyPro"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read().decode("utf-8"))
        return jsonify({"ok": True, "hint": result["choices"][0]["message"]["content"].strip()})
    except urllib.error.HTTPError as e:
        err = e.read().decode()
        print(f"Hint error {e.code}: {err}")
        return jsonify({"ok": False, "error": f"OpenRouter {e.code}: {err}"}), 502
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 502


@app.route("/api/ai/explain", methods=["POST"])
def api_ai_explain():
    import urllib.request, urllib.error
    body     = request.json
    question = body.get("question", "")
    answer   = body.get("answer", "")
    api_key  = os.getenv("OPENROUTER_API_KEY") or OPENROUTER_API_KEY
    if not api_key: return jsonify({"ok": False, "error": "No API key found. Check your .env file."}), 500
    payload = json.dumps({"model": "openai/gpt-4o-mini", "messages": [
        {"role": "system", "content": "You are an expert tutor. Explain concepts clearly and concisely with examples. Keep under 4 sentences."},
        {"role": "user",   "content": f"Question: {question}\nAnswer: {answer}\n\nExplain this in more depth with an example."}
    ], "max_tokens": 250, "temperature": 0.6}).encode("utf-8")
    req = urllib.request.Request("https://openrouter.ai/api/v1/chat/completions", data=payload,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json",
                 "HTTP-Referer": "http://localhost:5000", "X-Title": "StudyPro"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read().decode("utf-8"))
        return jsonify({"ok": True, "explanation": result["choices"][0]["message"]["content"].strip()})
    except urllib.error.HTTPError as e:
        err = e.read().decode()
        print(f"Explain error {e.code}: {err}")
        return jsonify({"ok": False, "error": f"OpenRouter {e.code}: {err}"}), 502
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 502

# ─────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 50)
    print("  Student Study Planner")
    print("  Open: http://localhost:5000")
    print("=" * 50)
    app.run(debug=True, port=5000)
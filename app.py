"""
Student Study Planner - Flask Web Application with Supabase
"""

from flask import Flask, render_template, request, jsonify
import json
import os
from datetime import datetime, date, timedelta
from dotenv import load_dotenv
import requests as req_lib

load_dotenv()

app = Flask(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")

# ─────────────────────────────────────────────
# Supabase helpers
# ─────────────────────────────────────────────

def sb_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }

def sb_get(table, params=""):
    url = f"{SUPABASE_URL}/rest/v1/{table}?{params}"
    r = req_lib.get(url, headers=sb_headers())
    return r.json()

def sb_post(table, data):
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    r = req_lib.post(url, headers=sb_headers(), json=data)
    result = r.json()
    return result[0] if isinstance(result, list) and result else result

def sb_patch(table, match_param, data):
    url = f"{SUPABASE_URL}/rest/v1/{table}?{match_param}"
    r = req_lib.patch(url, headers=sb_headers(), json=data)
    return r.json()

def sb_delete(table, match_param):
    url = f"{SUPABASE_URL}/rest/v1/{table}?{match_param}"
    r = req_lib.delete(url, headers=sb_headers())
    return r.status_code

# ─────────────────────────────────────────────
# Utility
# ─────────────────────────────────────────────

FALLBACK_SUBJECT = {"id": 0, "name": "Unknown", "color": "purple", "goal": 1}

def safe_subject(subject_map, subject_id):
    return subject_map.get(int(subject_id), FALLBACK_SUBJECT)

def session_minutes(session):
    try:
        sh, sm = map(int, session["start_time"].split(":"))
        eh, em = map(int, session["end_time"].split(":"))
        return max(0, (eh * 60 + em) - (sh * 60 + sm))
    except Exception:
        return 0

def calc_subject_hours(sessions, study_log):
    hours = {}
    for s in sessions:
        sid = s["subject_id"]
        hours[sid] = hours.get(sid, 0) + session_minutes(s) / 60
    for log in study_log:
        sid = log["subject_id"]
        hours[sid] = hours.get(sid, 0) + log["duration_min"] / 60
    return hours

def week_bounds():
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    return monday, sunday

def get_pomodoro_count():
    rows = sb_get("app_state", "key=eq.pomodoro_count")
    if rows and isinstance(rows, list):
        return int(rows[0]["value"])
    return 0

# ─────────────────────────────────────────────
# Page routes
# ─────────────────────────────────────────────

@app.route("/")
def dashboard():
    today_str = date.today().isoformat()
    today_name = date.today().strftime("%A, %B %d, %Y")

    subjects = sb_get("subjects", "order=id")
    sessions = sb_get("sessions", "order=date.desc")
    tasks = sb_get("tasks", "order=due")
    flashcards = sb_get("flashcards", "")
    study_log = sb_get("study_log", "")
    pomodoro_count = get_pomodoro_count()

    subject_map = {s["id"]: s for s in subjects}
    hours = calc_subject_hours(sessions, study_log)

    today_sessions = [s for s in sessions if s["date"] == today_str]
    for s in today_sessions:
        s["subject"] = safe_subject(subject_map, s["subject_id"])
        s["duration_min"] = session_minutes(s)
        s["start"] = s["start_time"]
        s["end"] = s["end_time"]

    pending_tasks = [t for t in tasks if not t["done"]][:5]
    for t in pending_tasks:
        t["subject"] = safe_subject(subject_map, t["subject_id"])

    total_hours = round(sum(hours.values()), 1)
    total_sessions = len(sessions)
    pending_count = sum(1 for t in tasks if not t["done"])
    fc_count = len(flashcards)

    subject_progress = []
    for s in subjects:
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
        pomodoro_count=pomodoro_count,
    )

@app.route("/planner")
def planner():
    subjects = sb_get("subjects", "order=id")
    sessions = sb_get("sessions", "order=date.desc,start_time")
    subject_map = {s["id"]: s for s in subjects}
    monday, sunday = week_bounds()

    week_days = []
    for i in range(7):
        day = monday + timedelta(days=i)
        day_str = day.isoformat()
        day_sessions = [s for s in sessions if s["date"] == day_str]
        for s in day_sessions:
            s["subject"] = safe_subject(subject_map, s["subject_id"])
            s["start"] = s["start_time"]
            s["end"] = s["end_time"]
        week_days.append({
            "name": day.strftime("%a"),
            "date": day_str,
            "short_date": day.strftime("%d"),
            "is_today": day_str == date.today().isoformat(),
            "sessions": sorted(day_sessions, key=lambda x: x["start_time"]),
        })

    all_sessions = sorted(sessions, key=lambda x: (x["date"], x["start_time"]), reverse=True)
    for s in all_sessions:
        s["subject"] = safe_subject(subject_map, s["subject_id"])
        s["duration_min"] = session_minutes(s)
        s["start"] = s["start_time"]
        s["end"] = s["end_time"]

    return render_template("planner.html",
        week_days=week_days,
        all_sessions=all_sessions,
        subjects=subjects,
        today=date.today().isoformat(),
    )

@app.route("/subjects")
def subjects_page():
    subjects = sb_get("subjects", "order=id")
    sessions = sb_get("sessions", "")
    study_log = sb_get("study_log", "")
    hours = calc_subject_hours(sessions, study_log)
    enriched = []
    for s in subjects:
        h = round(hours.get(s["id"], 0), 1)
        pct = min(100, round((h / max(s["goal"], 1)) * 100))
        enriched.append({**s, "studied": h, "pct": pct})
    return render_template("subjects.html", subjects=enriched)

@app.route("/tasks")
def tasks():
    subjects = sb_get("subjects", "order=id")
    tasks_list = sb_get("tasks", "order=due")
    subject_map = {s["id"]: s for s in subjects}
    today_str = date.today().isoformat()
    pending, done = [], []
    for t in tasks_list:
        t["subject"] = safe_subject(subject_map, t["subject_id"])
        t["overdue"] = (not t["done"]) and t.get("due", "") < today_str
        (done if t["done"] else pending).append(t)
    pending.sort(key=lambda x: (x.get("due", ""), x["priority"]))
    return render_template("tasks.html",
        pending=pending, done=done, subjects=subjects)

@app.route("/timer")
def timer():
    subjects = sb_get("subjects", "order=id")
    study_log = sb_get("study_log", "order=id.desc&limit=10")
    subject_map = {s["id"]: s for s in subjects}
    for log in study_log:
        log["subject"] = safe_subject(subject_map, log["subject_id"])
    pomodoro_count = get_pomodoro_count()
    return render_template("timer.html",
        subjects=subjects,
        recent_log=study_log,
        pomodoro_count=pomodoro_count,
    )

@app.route("/flashcards")
def flashcards():
    subjects = sb_get("subjects", "order=id")
    all_cards = sb_get("flashcards", "order=id")
    subject_map = {s["id"]: s for s in subjects}
    by_subject = {}
    for fc in all_cards:
        sid = fc["subject_id"]
        by_subject.setdefault(sid, []).append(fc)
    groups = []
    for sid, cards in by_subject.items():
        sub = safe_subject(subject_map, sid)
        known = sum(1 for c in cards if c["score"] > 0)
        groups.append({"subject": sub, "cards": cards, "known": known})
    return render_template("flashcards.html",
        groups=groups, subjects=subjects)

@app.route("/progress")
def progress():
    subjects = sb_get("subjects", "order=id")
    sessions = sb_get("sessions", "order=date.desc")
    tasks_list = sb_get("tasks", "")
    flashcards_list = sb_get("flashcards", "")
    study_log = sb_get("study_log", "")
    pomodoro_count = get_pomodoro_count()

    subject_map = {s["id"]: s for s in subjects}
    hours = calc_subject_hours(sessions, study_log)
    monday, _ = week_bounds()

    subject_stats = []
    for s in subjects:
        h = round(hours.get(s["id"], 0), 1)
        pct = min(100, round((h / max(s["goal"], 1)) * 100))
        subject_stats.append({**s, "studied": h, "pct": pct})

    week_activity = []
    for i in range(7):
        day = monday + timedelta(days=i)
        day_str = day.isoformat()
        count = sum(1 for s in sessions if s["date"] == day_str)
        mins = sum(session_minutes(s) for s in sessions if s["date"] == day_str)
        week_activity.append({
            "name": day.strftime("%a"),
            "date": day_str,
            "count": count,
            "mins": mins,
            "is_today": day_str == date.today().isoformat(),
        })

    all_sessions = sorted(sessions, key=lambda x: (x["date"], x["start_time"]), reverse=True)
    for s in all_sessions:
        s["subject"] = safe_subject(subject_map, s["subject_id"])
        s["duration_min"] = session_minutes(s)
        s["start"] = s["start_time"]
        s["end"] = s["end_time"]

    total_hours = round(sum(hours.values()), 1)
    done_tasks = sum(1 for t in tasks_list if t["done"])
    total_tasks = len(tasks_list)
    fc_mastered = sum(1 for f in flashcards_list if f["score"] > 0)

    return render_template("progress.html",
        subject_stats=subject_stats,
        week_activity=week_activity,
        all_sessions=all_sessions,
        total_hours=total_hours,
        done_tasks=done_tasks,
        total_tasks=total_tasks,
        fc_mastered=fc_mastered,
        pomodoro_count=pomodoro_count,
    )

# ─────────────────────────────────────────────
# API routes (JSON)
# ─────────────────────────────────────────────

@app.route("/api/sessions", methods=["POST"])
def api_add_session():
    body = request.json
    result = sb_post("sessions", {
        "subject_id": int(body["subject_id"]),
        "date": body["date"],
        "start_time": body["start"],
        "end_time": body["end"],
        "notes": body.get("notes", ""),
    })
    return jsonify({"ok": True, "id": result.get("id")})

@app.route("/api/sessions/<int:sid>", methods=["DELETE"])
def api_delete_session(sid):
    sb_delete("sessions", f"id=eq.{sid}")
    return jsonify({"ok": True})

@app.route("/api/subjects", methods=["POST"])
def api_add_subject():
    body = request.json
    result = sb_post("subjects", {
        "name": body["name"],
        "color": body.get("color", "purple"),
        "goal": int(body.get("goal", 5)),
    })
    return jsonify({"ok": True, "id": result.get("id")})

@app.route("/api/subjects/<int:sid>", methods=["DELETE"])
def api_delete_subject(sid):
    sb_delete("subjects", f"id=eq.{sid}")
    return jsonify({"ok": True})

@app.route("/api/tasks", methods=["POST"])
def api_add_task():
    body = request.json
    result = sb_post("tasks", {
        "title": body["title"],
        "subject_id": int(body["subject_id"]),
        "due": body.get("due", ""),
        "priority": body.get("priority", "Medium"),
        "done": False,
    })
    return jsonify({"ok": True, "id": result.get("id")})

@app.route("/api/tasks/<int:tid>/toggle", methods=["POST"])
def api_toggle_task(tid):
    current = sb_get("tasks", f"id=eq.{tid}")
    if current:
        new_done = not current[0]["done"]
        sb_patch("tasks", f"id=eq.{tid}", {"done": new_done})
    return jsonify({"ok": True})

@app.route("/api/tasks/<int:tid>", methods=["DELETE"])
def api_delete_task(tid):
    sb_delete("tasks", f"id=eq.{tid}")
    return jsonify({"ok": True})

@app.route("/api/flashcards", methods=["POST"])
def api_add_flashcard():
    body = request.json
    result = sb_post("flashcards", {
        "subject_id": int(body["subject_id"]),
        "question": body["question"],
        "answer": body["answer"],
        "score": 0,
    })
    return jsonify({"ok": True, "id": result.get("id")})

@app.route("/api/flashcards/<int:fid>", methods=["DELETE"])
def api_delete_flashcard(fid):
    sb_delete("flashcards", f"id=eq.{fid}")
    return jsonify({"ok": True})

@app.route("/api/flashcards/<int:fid>/score", methods=["POST"])
def api_score_flashcard(fid):
    body = request.json
    current = sb_get("flashcards", f"id=eq.{fid}")
    if current:
        new_score = max(0, current[0]["score"] + (1 if body.get("correct") else -1))
        sb_patch("flashcards", f"id=eq.{fid}", {"score": new_score})
    return jsonify({"ok": True})

@app.route("/api/study_log", methods=["POST"])
def api_add_study_log():
    body = request.json
    result = sb_post("study_log", {
        "subject_id": int(body["subject_id"]),
        "duration_min": int(body["duration_min"]),
        "note": body.get("note", ""),
        "date": date.today().isoformat(),
    })
    return jsonify({"ok": True})

@app.route("/api/pomodoro_complete", methods=["POST"])
def api_pomodoro_complete():
    count = get_pomodoro_count() + 1
    sb_patch("app_state", "key=eq.pomodoro_count", {"value": str(count)})
    return jsonify({"ok": True, "count": count})

# ─────────────────────────────────────────────
# AI Routes (OpenRouter)
# ─────────────────────────────────────────────

@app.route("/api/ai/generate_flashcards", methods=["POST"])
def api_generate_flashcards():
    body = request.json
    topic = body.get("topic", "").strip()
    subject_id = int(body.get("subject_id", 0))
    count = int(body.get("count", 5))
    difficulty = body.get("difficulty", "medium")
    api_key = os.getenv("OPENROUTER_API_KEY") or OPENROUTER_API_KEY
    if not topic:
        return jsonify({"ok": False, "error": "Topic is required"}), 400
    if not api_key:
        return jsonify({"ok": False, "error": "No API key found"}), 500

    prompt = f"""Generate exactly {count} flashcard question-answer pairs about: "{topic}"
Difficulty level: {difficulty}
Rules:
- Each card must have a clear, specific question and a concise accurate answer
- Questions should test understanding, not just memorization
- Answers should be 1-3 sentences max
- Cover different aspects of the topic
Respond ONLY with valid JSON in this exact format, no other text:
{{"cards": [{{"question": "...", "answer": "..."}}, {{"question": "...", "answer": "..."}}]}}"""

    try:
        resp = req_lib.post("https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://study-planner-self-one.vercel.app",
                "X-Title": "StudyPro"
            },
            json={
                "model": "openai/gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": "You are an expert educator who creates high-quality study flashcards. Always respond with valid JSON only."},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 1500,
                "temperature": 0.7
            },
            timeout=25)
        if resp.status_code != 200:
            return jsonify({"ok": False, "error": f"OpenRouter {resp.status_code}: {resp.text}"}), 502
        result = resp.json()
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 502

    try:
        content = result["choices"][0]["message"]["content"].strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        cards_data = json.loads(content.strip())
        cards = cards_data["cards"]
    except Exception as e:
        return jsonify({"ok": False, "error": f"Failed to parse AI response: {e}"}), 500

    saved = []
    for c in cards:
        fc = sb_post("flashcards", {
            "subject_id": subject_id,
            "question": c["question"],
            "answer": c["answer"],
            "score": 0
        })
        saved.append(fc)
    return jsonify({"ok": True, "cards": saved, "count": len(saved)})


@app.route("/api/ai/hint", methods=["POST"])
def api_ai_hint():
    body = request.json
    question = body.get("question", "")
    api_key = os.getenv("OPENROUTER_API_KEY") or OPENROUTER_API_KEY
    if not api_key:
        return jsonify({"ok": False, "error": "No API key found"}), 500
    try:
        resp = req_lib.post("https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json",
                     "HTTP-Referer": "https://study-planner-self-one.vercel.app", "X-Title": "StudyPro"},
            json={"model": "openai/gpt-4o-mini", "messages": [
                {"role": "system", "content": "You are a helpful tutor. Give a hint that guides toward the answer WITHOUT revealing it. Keep to 1-2 sentences."},
                {"role": "user", "content": f"Give me a hint for: {question}"}
            ], "max_tokens": 150, "temperature": 0.6},
            timeout=15)
        if resp.status_code != 200:
            return jsonify({"ok": False, "error": f"OpenRouter {resp.status_code}"}), 502
        result = resp.json()
        return jsonify({"ok": True, "hint": result["choices"][0]["message"]["content"].strip()})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 502


@app.route("/api/ai/explain", methods=["POST"])
def api_ai_explain():
    body = request.json
    question = body.get("question", "")
    answer = body.get("answer", "")
    api_key = os.getenv("OPENROUTER_API_KEY") or OPENROUTER_API_KEY
    if not api_key:
        return jsonify({"ok": False, "error": "No API key found"}), 500
    try:
        resp = req_lib.post("https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json",
                     "HTTP-Referer": "https://study-planner-self-one.vercel.app", "X-Title": "StudyPro"},
            json={"model": "openai/gpt-4o-mini", "messages": [
                {"role": "system", "content": "You are an expert tutor. Explain concepts clearly and concisely with examples. Keep under 4 sentences."},
                {"role": "user", "content": f"Question: {question}\nAnswer: {answer}\n\nExplain this in more depth with an example."}
            ], "max_tokens": 250, "temperature": 0.6},
            timeout=15)
        if resp.status_code != 200:
            return jsonify({"ok": False, "error": f"OpenRouter {resp.status_code}"}), 502
        result = resp.json()
        return jsonify({"ok": True, "explanation": result["choices"][0]["message"]["content"].strip()})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 502


if __name__ == "__main__":
    print("=" * 50)
    print("  Student Study Planner")
    print("  Open: http://localhost:5000")
    print("=" * 50)
    app.run(debug=True, port=5000)
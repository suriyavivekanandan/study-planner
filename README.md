# 📚 Student Study Planner

A full-featured study planner web app built with Python (Flask).

## Features
- **Dashboard** — overview of hours, sessions, tasks, and subject progress
- **Planner** — weekly calendar + full session list with add/delete
- **Subjects** — manage subjects with color coding and weekly hour goals
- **Tasks** — track assignments with priority, due dates, and completion
- **Focus Timer** — Pomodoro (25 min) + break (5 min) timer with animated rings
- **Flashcards** — create Q&A cards, flip to reveal, rate yourself (Again/Hard/Got it)
- **Progress** — bar charts, weekly activity, and full session history

All data is saved locally to `data.json` — no database required.

---

## Setup

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Run the app
```bash
python app.py
```

### 3. Open in browser
```
http://localhost:5000
```

---

## Project Structure
```
study_planner/
├── app.py              # Flask backend (routes + API)
├── requirements.txt    # Python dependencies
├── data.json           # Auto-created on first run
└── templates/
    ├── base.html       # Shared layout + nav + CSS
    ├── dashboard.html  # Home overview
    ├── planner.html    # Weekly planner
    ├── subjects.html   # Subject management
    ├── tasks.html      # Task list
    ├── timer.html      # Pomodoro timer
    ├── flashcards.html # Flashcard review
    └── progress.html   # Analytics
```

## Tech Stack
- **Backend**: Python 3 + Flask
- **Frontend**: Vanilla HTML/CSS/JS (no framework)
- **Storage**: JSON file (no database needed)
- **Icons**: Tabler Icons (CDN)

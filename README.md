# 🧠 MindGame — AI Personality Mind Game

> 🎪 **Just for fun — entertainment only. Not a psychological diagnosis, not science.**

Scenario-based personality discovery powered by live AI (Groq `openai/gpt-oss-120b`).
Answer 6 vivid scenarios → get a playful archetype reveal with a shareable result card.

## Features
- 6 AI-generated scenarios with 4 choice cards each, animated progression + progress bar
- Archetype, strengths, decision/problem-solving/communication styles, fun weaknesses, character description
- Reveal animation, copy result, Play Again

## Requirements
- Python 3.10+
- A free Groq API key ([console.groq.com/keys](https://console.groq.com/keys))
- Internet (AI calls go to Groq)

## Installation
```bash
python -m venv .venv
# Windows: .venv\Scripts\activate | macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env   # add GROQ_API_KEY  (or paste the key in Settings later)
```

## How to play
1. Press **Start Game**, pick a choice card per scenario (6 total)
2. Press **Reveal** for your archetype result card
3. Copy/share it, or Play Again for a fresh run

## Limitations
- Entertainment only — not psychology or science
- Needs a Groq key + internet; single in-memory session (restart clears it)

## Run (port 8011)

```bash
pip install -r requirements.txt
uvicorn app:app --port 8011
# open http://127.0.0.1:8011
```

## API key
- Click **⚙️ Settings** → paste Groq key → backend verifies via `models.list`, keeps it in **process memory only**.
- `DELETE /api/key` forgets it. `.env` (`GROQ_API_KEY=`) fallback supported.
- `GET /api/status` returns presence only. Frontend never stores/sends keys.

## API
- `POST /api/start` → `{scenarios[6]: {scenario, choices[4]}, total}`
- `POST /api/choice {index:0-3}` → `{recorded, total, done, next}`
- `POST /api/reveal` → `{archetype, title, strengths[], decision_style, problem_solving, communication, fun_weaknesses[], signature_traits[], character_description}`
- `GET /api/state`, `GET /api/status`

## Tests
```bash
pytest -q
```

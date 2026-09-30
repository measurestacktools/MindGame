# 🧠 MindGame — AI Personality Mind Game

> 🎪 **Just for fun — entertainment only. Not a psychological diagnosis, not science.**

Scenario-based personality discovery powered by live AI (Groq `openai/gpt-oss-120b`).
Answer 6 vivid scenarios → get a playful archetype reveal with a shareable result card.

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

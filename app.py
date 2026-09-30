"""MindGame — AI Personality / Mind Game (entertainment only)."""
import json
import os
import re
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from openai import OpenAI, OpenAIError
from pydantic import BaseModel, Field

load_dotenv()

MODEL = "openai/gpt-oss-120b"
BASE_URL = "https://api.groq.com/openai/v1"
TOTAL_ROUNDS = 6

app = FastAPI(title="MindGame")

# Process-global server memory only (never persisted to disk).
_api_key_memory: Optional[str] = None

# Single-session game state (single player, entertainment game).
_game: Dict[str, Any] = {"scenarios": [], "choices": []}


def get_effective_key() -> Optional[str]:
    if _api_key_memory:
        return _api_key_memory
    env_key = os.getenv("GROQ_API_KEY", "").strip()
    return env_key or None


def key_source() -> str:
    if _api_key_memory:
        return "memory"
    if os.getenv("GROQ_API_KEY", "").strip():
        return "env"
    return "none"


def map_groq_error(exc: Exception) -> str:
    msg = str(exc)
    low = msg.lower()
    if "401" in msg or "unauthorized" in low or "invalid api key" in low or "invalid_api_key" in low:
        return "That API key was rejected. Double-check it and try again."
    if "429" in msg or "rate limit" in low or "rate_limit" in low:
        return "Groq rate limit hit. Wait a minute, then try again."
    if "timeout" in low or "timed out" in low:
        return "Groq timed out. Check your connection and try again."
    if "connection" in low or "unreachable" in low or "dns" in low:
        return "Could not reach Groq. Check your internet and try again."
    if "model" in low and ("not found" in low or "404" in msg):
        return "Model unavailable right now. Try again in a bit."
    return "AI request failed. Try again in a moment."


def parse_json_safe(text: str) -> Any:
    """Parse JSON with fallbacks: strip fences, extract largest {...} block."""
    if text is None:
        raise ValueError("Empty AI response.")
    t = str(text).strip()
    # Strip markdown fences
    fence = re.search(r"```(?:json)?\s*(.*?)```", t, re.DOTALL | re.IGNORECASE)
    if fence:
        t = fence.group(1).strip()
    try:
        return json.loads(t)
    except Exception:
        pass
    # Fallback: largest balanced {...} substring
    start = t.find("{")
    end = t.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = t[start : end + 1]
        try:
            return json.loads(candidate)
        except Exception:
            pass
        # Last resort: try to fix trailing commas
        fixed = re.sub(r",\s*([}\]])", r"\1", candidate)
        return json.loads(fixed)
    raise ValueError("Could not understand the AI response. Please try again.")


def make_client(api_key: str) -> OpenAI:
    return OpenAI(api_key=api_key, base_url=BASE_URL, timeout=60.0)


START_SYSTEM = (
    "You are a playful game master for a personality discovery party game. "
    "This is entertainment only, just for fun — never clinical, diagnostic, or scientific. "
    "Generate imaginative everyday scenarios. Respond with JSON only."
)
START_USER = (
    "Generate exactly 6 vivid, fun, family-friendly scenarios for a personality mind game. "
    "Each scenario is 2-3 sentences, second person, varied settings "
    "(e.g. stranded road trip, mysterious package, time machine, talent show, tiny alien cafe, stormy cabin). "
    "Each scenario has exactly 4 distinct choice cards (short, punchy, <= 18 words each), "
    "each reflecting a different instinct (bold / thoughtful / playful / kind). "
    "Respond with JSON ONLY in this exact shape:\n"
    '{"scenarios": [{"scenario": "...", "choices": ["...", "...", "...", "..."]}]}'
)

REVEAL_SYSTEM = (
    "You are a warm, witty entertainer writing a fun personality reveal. "
    "This is entertainment only — just for fun, never a diagnosis and never scientific. "
    "Be positive, playful, and specific to the player's actual picks. Respond with JSON only."
)


def build_reveal_prompt(scenarios: List[Dict], choices: List[int]) -> str:
    lines = []
    for i, (sc, ci) in enumerate(zip(scenarios, choices)):
        choice_text = sc["choices"][ci]
        lines.append(f"Q{i+1}: {sc['scenario']}\nPicked: {choice_text}")
    joined = "\n\n".join(lines)
    return (
        "A player just answered 6 scenario questions in a for-fun personality mind game. "
        "Their picks:\n\n" + joined + "\n\n"
        "Write a personalized, playful result that clearly references their actual picks "
        "(mention at least 2 specific choices). Keep it kind and fun. "
        "Respond with JSON ONLY in this exact shape:\n"
        '{"archetype": "short catchy archetype name, e.g. The Lantern Navigator", '
        '"title": "one fun tagline sentence", '
        '"strengths": ["...", "...", "..."], '
        '"decision_style": "2-3 sentences", '
        '"problem_solving": "2-3 sentences", '
        '"communication": "2-3 sentences", '
        '"fun_weaknesses": ["...", "..."], '
        '"signature_traits": ["...", "...", "..."], '
        '"character_description": "3-5 vivid sentences painting their character"}'
    )


def validate_start_payload(data: Any) -> List[Dict]:
    if not isinstance(data, dict) or "scenarios" not in data:
        raise ValueError("bad shape")
    scenarios = data["scenarios"]
    if not isinstance(scenarios, list) or len(scenarios) != TOTAL_ROUNDS:
        raise ValueError("bad shape")
    cleaned: List[Dict] = []
    for s in scenarios:
        if not isinstance(s, dict):
            raise ValueError("bad shape")
        text = str(s.get("scenario", "")).strip()
        ch = s.get("choices")
        if not text or not isinstance(ch, list) or len(ch) != 4:
            raise ValueError("bad shape")
        choices = [str(c).strip() for c in ch]
        if any(not c for c in choices):
            raise ValueError("bad shape")
        cleaned.append({"scenario": text, "choices": choices})
    return cleaned


def validate_reveal_payload(data: Any) -> Dict:
    required = ["archetype", "title", "strengths", "decision_style",
                "problem_solving", "communication", "fun_weaknesses",
                "signature_traits", "character_description"]
    if not isinstance(data, dict):
        raise ValueError("bad shape")
    for k in required:
        if k not in data or data[k] in (None, "", []):
            raise ValueError(f"missing '{k}'")
    for k in ["strengths", "fun_weaknesses", "signature_traits"]:
        if not isinstance(data[k], list) or not data[k]:
            raise ValueError(f"bad '{k}'")
        data[k] = [str(x).strip() for x in data[k] if str(x).strip()]
    for k in ["archetype", "title", "decision_style", "problem_solving", "communication", "character_description"]:
        data[k] = str(data[k]).strip()
    return data


class KeyIn(BaseModel):
    key: str = Field(min_length=5, max_length=300)


class ChoiceIn(BaseModel):
    index: int


@app.get("/api/status")
def api_status():
    key = get_effective_key()
    return {"has_key": bool(key), "model": MODEL, "source": key_source()}


@app.post("/api/key")
def api_set_key(body: KeyIn):
    global _api_key_memory
    key = body.key.strip()
    if not key:
        return JSONResponse({"error": "Please paste a valid key."}, status_code=400)
    try:
        client = make_client(key)
        client.models.list()
    except Exception as exc:  # noqa: BLE001
        return JSONResponse({"error": map_groq_error(exc)}, status_code=401)
    _api_key_memory = key
    return {"ok": True, "source": "memory"}


@app.delete("/api/key")
def api_delete_key():
    global _api_key_memory
    _api_key_memory = None
    key = get_effective_key()
    return {"ok": True, "has_key": bool(key), "source": key_source()}


@app.post("/api/start")
def api_start():
    key = get_effective_key()
    if not key:
        return JSONResponse({"error": "No API key. Open Settings and add your Groq key first."}, status_code=400)
    try:
        client = make_client(key)
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": START_SYSTEM},
                {"role": "user", "content": START_USER},
            ],
            temperature=0.9,
            max_tokens=2500,
            response_format={"type": "json_object"},
        )
        raw = resp.choices[0].message.content or ""
        data = parse_json_safe(raw)
        scenarios = validate_start_payload(data)
    except ValueError as exc:
        return JSONResponse({"error": f"AI gave an odd response ({exc}). Tap Start again."}, status_code=502)
    except Exception as exc:  # noqa: BLE001
        return JSONResponse({"error": map_groq_error(exc)}, status_code=502)
    _game["scenarios"] = scenarios
    _game["choices"] = []
    return {"scenarios": scenarios, "total": TOTAL_ROUNDS}


@app.post("/api/choice")
def api_choice(body: ChoiceIn):
    scenarios = _game.get("scenarios", [])
    choices: List[int] = _game.get("choices", [])
    if not scenarios:
        return JSONResponse({"error": "Tap Start first to get your scenarios."}, status_code=400)
    if len(choices) >= TOTAL_ROUNDS:
        return JSONResponse({"error": "All 6 answers are in. Hit Reveal!."}, status_code=400)
    if body.index < 0 or body.index > 3:
        return JSONResponse({"error": "Pick one of the 4 cards (index 0-3)."}, status_code=400)
    choices.append(body.index)
    _game["choices"] = choices
    done = len(choices) >= TOTAL_ROUNDS
    return {"recorded": len(choices), "total": TOTAL_ROUNDS, "done": done,
            "next": None if done else scenarios[len(choices)]}


@app.get("/api/state")
def api_state():
    scenarios = _game.get("scenarios", [])
    choices: List[int] = _game.get("choices", [])
    out = {"total": TOTAL_ROUNDS, "answered": len(choices), "started": bool(scenarios)}
    if scenarios and len(choices) < len(scenarios):
        out["current"] = scenarios[len(choices)]  # type: ignore
    return out


@app.post("/api/reveal")
def api_reveal():
    key = get_effective_key()
    if not key:
        return JSONResponse({"error": "No API key. Open Settings and add your Groq key first."}, status_code=400)
    scenarios = _game.get("scenarios", [])
    choices: List[int] = _game.get("choices", [])
    if not scenarios or len(choices) < TOTAL_ROUNDS:
        return JSONResponse(
            {"error": f"Answer all {TOTAL_ROUNDS} scenarios first ({len(choices)}/{TOTAL_ROUNDS} done)."},
            status_code=400,
        )
    try:
        client = make_client(key)
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": REVEAL_SYSTEM},
                {"role": "user", "content": build_reveal_prompt(scenarios, choices)},
            ],
            temperature=0.85,
            max_tokens=2000,
            response_format={"type": "json_object"},
        )
        raw = resp.choices[0].message.content or ""
        data = parse_json_safe(raw)
        result = validate_reveal_payload(data)
    except ValueError as exc:
        return JSONResponse({"error": f"AI gave an odd response ({exc}). Try Reveal again."}, status_code=502)
    except Exception as exc:  # noqa: BLE001
        return JSONResponse({"error": map_groq_error(exc)}, status_code=502)
    picked_texts = [scenarios[i]["choices"][c] for i, c in enumerate(choices)]
    result["_picked"] = picked_texts
    return result


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
if os.path.isdir(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))

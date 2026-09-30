"""Tests: validation, state flow, JSON-parse fallbacks (mocked, no live key)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient  # noqa: E402

import app as mg  # noqa: E402


def make_client():
    return TestClient(mg.app)


def fake_scenarios():
    return {"scenarios": [
        {"scenario": f"Scenario number {i+1} pulls you into a vivid twist.", "choices": [f"Choice {c+1} for Q{i+1}" for c in range(4)]}
        for i in range(6)
    ]}


def fake_result():
    return {
        "archetype": "The Lantern Navigator",
        "title": "Brave heart, curious mind.",
        "strengths": ["Courage", "Kindness", "Wit"],
        "decision_style": "You decide fast but kindly.",
        "problem_solving": "You break big puzzles into small steps.",
        "communication": "Warm, clear and playful.",
        "fun_weaknesses": ["Overpacks snacks", "Talks to houseplants"],
        "signature_traits": ["Curious", "Loyal", "Bold"],
        "character_description": "You charge toward mystery with a lantern and a laugh.",
    }


class FakeMsg:
    def __init__(self, content):
        self.content = content


class FakeChoice:
    def __init__(self, content):
        self.message = FakeMsg(content)


class FakeResp:
    def __init__(self, content):
        self.choices = [FakeChoice(content)]


class FakeCompletions:
    def __init__(self, content):
        self._content = content

    def create(self, **kwargs):
        return FakeResp(self._content)


class FakeChat:
    def __init__(self, content):
        self.completions = FakeCompletions(content)


class FakeClient:
    def __init__(self, content):
        self.chat = FakeChat(content)
        self._content = content

    def __call__(self, *a, **k):
        return self


def test_parse_json_safe_strips_fences():
    import json
    raw = '```json\n{"a": 1}\n```'
    assert mg.parse_json_safe(raw) == {"a": 1}
    raw2 = 'Here you go {"x": [1, 2,]} trailing'
    assert mg.parse_json_safe(raw2)["x"] == [1, 2]
    try:
        mg.parse_json_safe("no json here")
        assert False, "should raise"
    except ValueError:
        pass


def test_map_groq_error():
    assert "rejected" in mg.map_groq_error(Exception("401 Unauthorized")).lower()
    assert "rate limit" in mg.map_groq_error(Exception("429 rate_limit_exceeded")).lower()
    assert mg.map_groq_error(Exception("boom"))


def test_validate_start_rejects_bad():
    import pytest
    with pytest.raises(ValueError):
        mg.validate_start_payload({"scenarios": []})
    with pytest.raises(ValueError):
        mg.validate_reveal_payload({"archetype": "x"})


def test_state_flow_validation_and_happy_path(monkeypatch):
    import json
    c = make_client()
    # no scenarios yet -> choice fails
    mg._game["scenarios"] = []
    mg._game["choices"] = []
    r = c.post("/api/choice", json={"index": 0})
    assert r.status_code == 400
    # invalid index rejected
    mg._game["scenarios"] = fake_scenarios()["scenarios"]
    mg._game["choices"] = []
    r = c.post("/api/choice", json={"index": 9})
    assert r.status_code == 400
    # reveal before complete fails
    r = c.post("/api/reveal")
    assert r.status_code in (400,)
    # happy path with mocked Groq
    mg._api_key_memory = "test-key"
    monkeypatch.setattr(mg, "make_client", lambda key: FakeClient(json.dumps(fake_scenarios())))
    r = c.post("/api/start")
    assert r.status_code == 200, r.text
    assert len(r.json()["scenarios"]) == 6
    for i in range(6):
        r = c.post("/api/choice", json={"index": i % 4})
        assert r.status_code == 200, r.text
    assert r.json()["done"] is True
    monkeypatch.setattr(mg, "make_client", lambda key: FakeClient(json.dumps(fake_result())))
    r = c.post("/api/reveal")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["archetype"] == "The Lantern Navigator"
    assert len(body["strengths"]) == 3
    mg._api_key_memory = None


def test_status_presence_only():
    c = make_client()
    mg._api_key_memory = None
    r = c.get("/api/status")
    assert "has_key" in r.json()
    assert "gsk_" not in r.text

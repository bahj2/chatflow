# Iteration 12: in-process check that /api/voice/test failure -> 424 JSON (HF demo forced to fail via monkeypatch)
import os
import sys
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, "/app/backend")
import server  # noqa: E402


@pytest.fixture(scope="module")
def client():
    async def boom(*a, **k):
        raise RuntimeError("HF 503")
    mp = pytest.MonkeyPatch()
    mp.setattr(server.M, "speak", boom)
    with TestClient(server.app) as c:
        tok = c.post("/api/auth/login", json={"email": "admin@replyflow.com", "password": "admin123"}).json()["token"]
        yield c, {"Authorization": f"Bearer {tok}"}
    mp.undo()


def test_khmer_failure_424(client):
    c, h = client
    r = c.post("/api/voice/test", headers=h, json={"text": "សួស្តីបង"})
    assert r.status_code == 424
    assert r.headers["content-type"].startswith("application/json")
    assert r.json()["detail"].startswith("The free VoxCPM2 Khmer voice (Hugging Face demo) is busy or down right now")


def test_english_failure_424(client):
    c, h = client
    r = c.post("/api/voice/test", headers=h, json={"text": "hello"})
    assert r.status_code == 424
    assert r.json()["detail"] == "Voice generation failed. Please try again."


# seller-voice: transcription failure -> 424 + no orphan media; empty transcript -> 400
def _count():
    from pymongo import MongoClient
    from dotenv import dotenv_values
    env = dotenv_values("/app/backend/.env")
    return MongoClient(env["MONGO_URL"])[env["DB_NAME"]].media.count_documents({"kind": "seller_voice"})


def _up(c, h):
    with open("/tmp/long.mp3", "rb") as f:
        return c.post("/api/settings/seller-voice", headers=h, files={"file": ("s.mp3", f, "audio/mpeg")}, data={"text": ""})


def test_transcribe_fail_424_no_orphan(client):
    c, h = client
    async def fail(*a, **k):
        raise RuntimeError("gemini+whisper down")
    mp = pytest.MonkeyPatch()
    mp.setattr(server.M, "transcribe", fail)
    before = _count()
    r = _up(c, h)
    mp.undo()
    assert r.status_code == 424
    assert r.json()["detail"].startswith("Could not write down the words")
    assert _count() == before


def test_empty_transcript_400(client):
    c, h = client
    async def empty(*a, **k):
        return "  "
    mp = pytest.MonkeyPatch()
    mp.setattr(server.M, "transcribe", empty)
    before = _count()
    r = _up(c, h)
    mp.undo()
    assert r.status_code == 400
    assert r.json()["detail"].startswith("No speech found in this sample")
    assert _count() == before

# Iteration 13: unit test of deliver() Telegram routing (sendPhoto / sendMediaGroup / sendMessage) with httpx mocked
import asyncio
import json
import sys

import pytest

sys.path.insert(0, "/app/backend")
import server  # noqa: E402

CALLS = []


class Resp:
    status_code, text = 200, "{}"


class FakeClient:
    def __init__(self, *a, **k):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def post(self, url, **kw):
        CALLS.append((url.rsplit("/", 1)[-1], kw))
        return Resp()


@pytest.fixture(autouse=True)
def patch(monkeypatch):
    CALLS.clear()
    monkeypatch.setattr(server.httpx, "AsyncClient", FakeClient)

    async def load(db, mid):
        return (b"IMG" + mid.encode(), {"content_type": "image/png"})
    monkeypatch.setattr(server.M, "load_media", load)


def prods(n_img, n_txt):
    return ([{"id": f"i{i}", "name": f"P{i}", "price": f"{i}$", "image_media_id": f"m{i}"} for i in range(n_img)] +
            [{"id": f"t{i}", "name": f"T{i}", "price": "", "image_media_id": ""} for i in range(n_txt)])


def run(products, voice=None):
    conv = {"channel": "telegram", "external_id": "123"}
    s = server.Settings(telegram_token="tok")
    asyncio.run(server.deliver(conv, s, "hello", voice, products))
    return [c[0] for c in CALLS]


def test_one_photo():
    assert run(prods(1, 0)) == ["sendMessage", "sendPhoto"]
    assert CALLS[1][1]["data"]["caption"] == "P0 — 0$"


def test_album():
    assert run(prods(4, 0)) == ["sendMessage", "sendMediaGroup"]
    media = json.loads(CALLS[1][1]["data"]["media"])
    assert [m["media"] for m in media] == ["attach://p0", "attach://p1", "attach://p2", "attach://p3"]
    assert media[2]["caption"] == "P2 — 2$" and set(CALLS[1][1]["files"]) == {"p0", "p1", "p2", "p3"}


def test_mixed_and_text_only():
    assert run(prods(2, 2)) == ["sendMessage", "sendMediaGroup", "sendMessage"]
    assert CALLS[2][1]["json"]["text"] == "T0\nT1"
    CALLS.clear()
    assert run(prods(0, 3)) == ["sendMessage", "sendMessage"]


def test_voice_with_photos():
    assert run(prods(3, 0), voice=b"mp3") == ["sendVoice", "sendMediaGroup"]


def test_split_show_cap_10():
    ps = [{"id": f"{i:02d}abcdefgh", "name": f"N{i}"} for i in range(14)]
    text = "We have stuff [[show:" + ",".join(p["id"][:8] for p in ps) + "]]"
    clean, picked = server.split_show(text, ps)
    assert len(picked) == 10 and "[[show" not in clean

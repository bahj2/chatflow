# Iteration 14: split_show markdown stripping + Telegram sendMediaGroup failure fallback (httpx mocked)
import asyncio
import sys

import pytest

sys.path.insert(0, "/app/backend")
import server  # noqa: E402

CALLS = []
STATUS = {}


class Resp:
    def __init__(self, code):
        self.status_code, self.text = code, "{}"


class FakeClient:
    def __init__(self, *a, **k):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def post(self, url, **kw):
        m = url.rsplit("/", 1)[-1]
        CALLS.append((m, kw))
        return Resp(STATUS.get(m, 200))


@pytest.fixture(autouse=True)
def patch(monkeypatch):
    CALLS.clear()
    STATUS.clear()
    monkeypatch.setattr(server.httpx, "AsyncClient", FakeClient)

    async def load(db, mid):
        return (b"IMG", {"content_type": "image/png"})
    monkeypatch.setattr(server.M, "load_media", load)


P = [{"id": "abcd1234xyz", "name": "Gemini Pro", "price": "10$"}]


# ---- markdown stripping ----
def test_bold_and_underline_removed():
    clean, picked = server.split_show("We sell **Gemini Pro** for __10$__ [[show:abcd1234]]", P)
    assert clean == "We sell Gemini Pro for 10$" and len(picked) == 1


def test_headings_and_list_markers():
    t = "# Our products\n## Menu\n* **Gemini Pro** - 10$\n- Canva Pro - 5$\n  * ChatGPT - 15$"
    clean, _ = server.split_show(t, P)
    assert "**" not in clean and "#" not in clean
    lines = clean.split("\n")
    assert lines[0] == "Our products" and lines[1] == "Menu"
    assert lines[2] == "• Gemini Pro - 10$" and lines[3] == "• Canva Pro - 5$"
    assert lines[4].strip() == "• ChatGPT - 15$"


def test_midline_untouched():
    for t in ["Prices are 10-15$ each", "We have 3 * 2 = 6 items", "Price - 5$ only", "C# course #1 available", "-5$ off today", "*note"]:
        assert server.split_show(t, P)[0] == t, t


def test_khmer_list():
    clean, _ = server.split_show("បងលក់:\n* **Gemini Pro** - 10$\n* Canva Pro - 5$ [[show:abcd1234]]", P)
    assert clean == "បងលក់:\n• Gemini Pro - 10$\n• Canva Pro - 5$"


def test_blank_line_before_list_preserved():
    # observation: ^\s* with re.M can swallow the preceding blank line
    clean, _ = server.split_show("Here you go:\n\n- A\n- B", P)
    print(repr(clean))
    assert "• A" in clean and "• B" in clean


def test_catalog_text_says_no_markdown():
    assert "never with ** or markdown" in server.catalog_text(P)


# ---- telegram album fallback ----
def prods(n_img, n_txt):
    return ([{"id": f"i{i}", "name": f"P{i}", "price": f"{i}$", "image_media_id": f"m{i}"} for i in range(n_img)] +
            [{"id": f"t{i}", "name": f"T{i}", "price": "", "image_media_id": ""} for i in range(n_txt)])


def run(products, voice=None):
    asyncio.run(server.deliver({"channel": "telegram", "external_id": "123"}, server.Settings(telegram_token="tok"), "hello", voice, products))
    return [c[0] for c in CALLS]


def test_album_fail_falls_back_to_text():
    STATUS["sendMediaGroup"] = 400
    assert run(prods(3, 0)) == ["sendMessage", "sendMediaGroup", "sendMessage"]
    assert CALLS[2][1]["json"]["text"] == "P0 — 0$\nP1 — 1$\nP2 — 2$"


def test_album_fail_mixed_one_text_message():
    STATUS["sendMediaGroup"] = 500
    assert run(prods(2, 2)) == ["sendMessage", "sendMediaGroup", "sendMessage"]
    assert CALLS[2][1]["json"]["text"] == "P0 — 0$\nP1 — 1$\nT0\nT1"


def test_album_fail_with_voice():
    STATUS["sendMediaGroup"] = 400
    assert run(prods(2, 0), voice=b"mp3") == ["sendVoice", "sendMediaGroup", "sendMessage"]


def test_album_ok_no_fallback():
    assert run(prods(3, 0)) == ["sendMessage", "sendMediaGroup"]

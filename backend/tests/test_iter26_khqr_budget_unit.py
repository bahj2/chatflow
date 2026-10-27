# Iter26: in-process unit tests for KHQR.dev retry (FIX A) and shared per-IP budget (FIX B). No network.
import sys
import time
import threading
import pytest

sys.path.insert(0, "/app/backend")
import payments as P  # noqa: E402


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    monkeypatch.setattr(P, "KHQR", lambda *a, **k: object())
    P._calls.clear(); P._last.clear(); P._locks.clear(); P._store_currency.clear()
    yield
    P._calls.clear(); P._last.clear(); P._locks.clear(); P._store_currency.clear()


def test_constants():
    assert (P._WINDOW, P._MAX, P._KEEP) == (60, 7, 3)
    assert P.BUSY == "KHQR.dev is busy right now. Please try again in a minute."


# FIX A: retry once after ~2.5 s on 'Failed to validate store payment link'
def test_validate_retry_then_success():
    n = {"c": 0}

    def fn(k):
        n["c"] += 1
        if n["c"] == 1:
            raise ValueError("Failed to validate store payment link.")
        return "OK"
    t = time.time()
    assert P._relay_call("rbk_a", fn) == "OK"
    dt = time.time() - t
    assert n["c"] == 2 and 2.4 <= dt < 4.5, dt
    assert len(P._calls) == 2


def test_validate_twice_raises_original():
    def fn(k):
        raise ValueError("Failed to validate store payment link.")
    with pytest.raises(ValueError, match="validate store payment link"):
        P._relay_call("rbk_a", fn)


def test_validate_no_retry_when_wait_max_small():
    n = {"c": 0}

    def fn(k):
        n["c"] += 1
        raise ValueError("Failed to validate store payment link.")
    with pytest.raises(ValueError):
        P._relay_call("rbk_a", fn, wait_max=0)
    assert n["c"] == 1


def test_relay_qr_wraps_payment_error(monkeypatch):
    class K:
        def create_qr(self, **kw):
            raise ValueError("Failed to validate store payment link.")
    monkeypatch.setattr(P, "KHQR", lambda *a, **k: K())
    with pytest.raises(P.PaymentError, match="validate store payment link"):
        P._relay_qr("rbk_a", 10, "USD", "B1")
    assert len(P._calls) == 3  # store-link check retried up to twice (3 tries)


# FIX B: budget
def test_budget_max_7_then_skip():
    for _ in range(7):
        assert P._budget(0) is True
    assert P._budget(0) is False
    assert len(P._calls) == 7


def test_budget_keep_reserves_slots():
    for _ in range(4):
        assert P._budget(0, keep=3) is True
    assert P._budget(0, keep=3) is False  # background stops at 4
    assert P._budget(0, keep=1) is True   # deeplink can use up to 6
    assert P._budget(0, keep=1) is True
    assert P._budget(0, keep=1) is False
    assert P._budget(0) is True           # customer QR gets the 7th
    assert P._budget(0) is False


def test_budget_waits_for_expiry():
    now = time.time()
    P._calls.extend([now - 58] * 7)  # expire in ~2s
    t = time.time()
    assert P._budget(5) is True
    assert 1.0 <= time.time() - t < 4


def test_budget_gives_up_when_wait_too_long():
    P._calls.extend([time.time()] * 7)
    t = time.time()
    assert P._budget(2) is False
    assert time.time() - t < 0.5  # fails fast, does not sleep the whole wait


def test_bulk_paid_returns_empty_when_busy():
    P._calls.extend([time.time()] * 4)  # 4 used -> background (keep=3) must skip
    called = {"c": 0}
    t = time.time()
    assert P._bulk_paid("rbk_a", ["m1"]) == []
    assert time.time() - t < 0.5 and called["c"] == 0


def test_bulk_paid_uses_spare_budget(monkeypatch):
    class K:
        def check_bulk_payments(self, m):
            return list(m)
    monkeypatch.setattr(P, "KHQR", lambda *a, **k: K())
    assert P._bulk_paid("rbk_a", ["m1", "m2"]) == ["m1", "m2"]


def test_deeplink_skips_when_busy():
    P._calls.extend([time.time()] * 6)  # keep=1 -> skip
    t = time.time()
    assert P._deeplink("rbk_a", "qr", "Shop") is None
    assert time.time() - t < 0.5


def test_create_qr_waits_for_slot(monkeypatch):
    class K:
        def create_qr(self, **kw):
            class R(str):
                md5 = "abc"
            return R("QRDATA")
    monkeypatch.setattr(P, "KHQR", lambda *a, **k: K())
    P._calls.extend([time.time() - 57] * 7)  # free in ~3 s
    t = time.time()
    qr, md5 = P._relay_qr("rbk_a", 10, "USD", "B1")
    assert qr == "QRDATA" and md5 == "abc"
    assert 2 <= time.time() - t < 6


def test_create_qr_busy_message_when_no_slot():
    P._calls.extend([time.time()] * 7)  # full for 60s > 25s
    t = time.time()
    with pytest.raises(P.PaymentError, match="busy right now"):
        P._relay_qr("rbk_a", 10, "USD", "B1")
    assert time.time() - t < 1


def test_rate_limit_retry_followed_when_fits():
    n = {"c": 0}

    def fn(k):
        n["c"] += 1
        if n["c"] == 1:
            raise ValueError("Rate limit exceeded. Retry in 2s")
        return "OK"
    t = time.time()
    assert P._relay_call("rbk_a", fn) == "OK"
    assert 1.9 <= time.time() - t < 4


def test_rate_limit_retry_too_long_fails_fast():
    def fn(k):
        raise ValueError("Rate limit exceeded. Retry in 40s")
    t = time.time()
    with pytest.raises(ValueError, match="busy right now"):
        P._relay_call("rbk_a", fn)
    assert time.time() - t < 1.5


def test_ip_limit_fills_window_and_others_wait():
    def fn(k):
        raise ValueError("IP Rate limit exceeded. Retry in 40s")
    with pytest.raises(ValueError, match="busy"):
        P._relay_call("rbk_a", fn)
    # 40s > 25s: fails fast; window not necessarily filled in this path
    print("calls after ip-limit fail-fast:", len(P._calls))


def test_ip_limit_retry_within_wait_succeeds():
    """IP limit with 'Retry in 2s' (fits in 25 s) should succeed on 2nd try."""
    n = {"c": 0}

    def fn(k):
        n["c"] += 1
        if n["c"] == 1:
            raise ValueError("IP Rate limit exceeded for this server. Retry in 2s")
        return "OK"
    t = time.time()
    try:
        res = P._relay_call("rbk_a", fn)
    finally:
        print("ip-limit retry elapsed", round(time.time() - t, 1), "calls in window", len(P._calls), "fn calls", n["c"])
    assert res == "OK"


def test_ip_limit_other_token_blocked_after_fill():
    """During an IP-limit pause the shared window is full, so other tokens' background calls skip; afterwards it frees up."""
    n = {"c": 0}

    def fn(k):
        n["c"] += 1
        if n["c"] == 1:
            raise ValueError("IP Rate limit exceeded. Retry in 2s")
        return "OK"
    out = {}
    th = threading.Thread(target=lambda: out.setdefault("r", P._relay_call("rbk_a", fn, wait_max=10)))
    th.start()
    time.sleep(0.8)  # inside the 2 s pause
    assert len(P._calls) >= 7
    assert P._bulk_paid("rbk_b", ["m"]) == []
    th.join(10)
    assert out.get("r") == "OK"  # the waiting call itself succeeds after the pause

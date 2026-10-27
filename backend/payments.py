"""Bakong KHQR payments: local QR (manual confirm) or KHQR.dev relay (automatic payment check)."""
import asyncio
import io
import os
import threading
from collections import deque
import re
import time

from bakong_khqr import KHQR
from PIL import Image

QR_MINUTES = 10
USD_KHR = float(os.environ.get("USD_KHR_RATE") or 4100)  # riel per dollar when a KHQR.dev store takes only one currency
RELAY_PREFIX = "rbk"
JWT_PREFIX = "eyJ"  # Bakong Open API token (api-bakong.nbc.gov.kh), valid 90 days
ACCOUNT_RE = re.compile(r"^[A-Za-z0-9._-]{2,40}@[A-Za-z0-9._-]{2,20}$")
_NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")


class PaymentError(Exception):
    pass


def jwt_valid(token: str) -> bool:
    """A Bakong Open API token that hasn't expired (checked from its own expiry date, no network call)."""
    import base64, json  # noqa: E401
    t = (token or "").strip()
    if not t.startswith(JWT_PREFIX) or t.count(".") != 2:
        return False
    try:
        exp = json.loads(base64.urlsafe_b64decode(t.split(".")[1] + "==")).get("exp", 0)
    except ValueError:
        return False
    return exp > time.time() + 60


def jwt_expiry(token: str) -> str:
    import base64, json  # noqa: E401
    try:
        exp = json.loads(base64.urlsafe_b64decode(token.split(".")[1] + "==")).get("exp", 0)
        return time.strftime("%d %b %Y", time.gmtime(exp)) if exp else ""
    except (ValueError, IndexError):
        return ""


def can_check(token: str) -> bool:
    """Payments can be confirmed automatically: KHQR.dev relay token, or a valid Bakong Open API token."""
    t = (token or "").strip()
    return t.startswith(RELAY_PREFIX) or jwt_valid(t)


def parse_price(text: str):
    """'10$' / '$2.75' -> (amount, 'USD'); '15,000៛' / '15000 riel' / 'KHR 5000' -> (amount, 'KHR'); ranges or no number -> None."""
    t = (text or "").strip()
    nums = _NUM.findall(t)
    if len(nums) != 1:
        return None
    amount = float(nums[0].replace(",", ""))
    if amount <= 0:
        return None
    khr = "៛" in t or re.search(r"riel|khr|រៀល", t, re.I)
    return (round(amount), "KHR") if khr else (round(amount, 2), "USD")


def _tlv(data: str) -> list:
    out, i = [], 0
    while i + 4 <= len(data):
        tag, n = data[i:i + 2], int(data[i + 2:i + 4])
        out.append((tag, data[i + 4:i + 4 + n]))
        i += 4 + n
    return out


def _crc16(data: str) -> str:
    crc = 0xFFFF
    for byte in data.encode("utf-8"):
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) if crc & 0x8000 else (crc << 1)
            crc &= 0xFFFF
    return format(crc, "04X")


def _with_expiry(qr: str, minutes: int) -> str:
    """The library only supports whole-day expiry; rewrite tag 99 so the QR itself expires after `minutes`."""
    now = int(time.time() * 1000)
    created, expires = str(now), str(now + minutes * 60_000)
    tag99 = f"00{len(created):02d}{created}01{len(expires):02d}{expires}"
    body = "".join(f"{t}{len(v):02d}{v}" if t != "99" else f"99{len(tag99):02d}{tag99}" for t, v in _tlv(qr[:-8]))
    body += "6304"
    return body + _crc16(body)


def _local_qr(account_id: str, merchant: str, city: str, amount: float, currency: str, bill: str) -> tuple:
    k = KHQR()
    qr = str(k.create_qr(account_id=account_id, merchant_name=merchant[:25], merchant_city=city[:15], amount=amount,
                         currency=currency, bill_number=bill, static=False, expiration=1))
    qr = _with_expiry(qr, QR_MINUTES)
    return qr, k.generate_md5(qr)


# KHQR.dev allows 1 request per second per token: space every call for the same token, retry once if still limited
# ...and 8 requests per 60 s per server IP for ALL shops together: one shared budget, a few slots kept for customer QRs
_GAP = 1.1
_WINDOW, _MAX, _KEEP = 60, 7, 3
_locks: dict = {}
_last: dict = {}
_calls: deque = deque()
_guard = threading.Lock()
BUSY = "KHQR.dev is busy right now. Please try again in a minute."


def _budget(wait_max: float, keep: int = 0) -> bool:
    """Reserve one KHQR.dev call in the shared per-IP window; wait up to wait_max seconds. keep = slots left for others."""
    deadline = time.time() + wait_max
    while True:
        with _guard:
            now = time.time()
            while _calls and _calls[0] < now - _WINDOW:
                _calls.popleft()
            if len(_calls) < _MAX - keep:
                _calls.append(now)
                return True
            wait = _calls[0] + _WINDOW - now if _calls else 1
        if time.time() + wait > deadline:
            return False
        time.sleep(min(wait, 1.0))


def _relay_call(token: str, fn, wait_max: float = 25, keep: int = 0):
    """wait_max 0 + keep: background work that simply skips when the budget is tight (raises ValueError(BUSY))."""
    with _guard:
        lock = _locks.setdefault(token, threading.Lock())
    with lock:
        start = time.time()
        for attempt in range(2):
            wait = _last.get(token, 0) + _GAP - time.time()
            if wait > 0:
                time.sleep(wait)
            if not _budget(max(0.0, wait_max - (time.time() - start)), keep):
                raise ValueError(BUSY)
            try:
                return fn(KHQR(token))
            except ValueError as e:
                msg = str(e).lower()
                left = wait_max - (time.time() - start)
                if attempt == 0 and "rate limit" in msg:
                    m = re.search(r"retry in (\d+)", msg)
                    pause = int(m.group(1)) if m else 2
                    if pause <= left:
                        if "ip rate limit" in msg:  # the whole server is over: fill the window so others wait too
                            with _guard:
                                _calls.extend([time.time()] * max(0, _MAX - len(_calls)))
                        time.sleep(pause)
                        continue
                    raise ValueError(BUSY)
                if attempt == 0 and "validate store payment link" in msg and left > 3:
                    time.sleep(2.5)  # KHQR.dev's store-link check fails now and then; a second try usually works
                    continue
                raise
            finally:
                _last[token] = time.time()


def _relay_qr(token: str, amount: float, currency: str, bill: str) -> tuple:
    try:
        res = _relay_call(token, lambda k: k.create_qr(amount=amount, currency=currency, bill_number=bill))
    except ValueError as e:
        raise PaymentError(str(e))
    return str(res), res.md5


def convert(amount: float, currency: str, to: str) -> tuple:
    if to == currency:
        return amount, currency
    if to == "KHR":
        return float(max(100, round(amount * USD_KHR / 100) * 100)), "KHR"  # whole hundreds of riel
    return round(amount / USD_KHR, 2), "USD"


_store_currency: dict = {}  # token -> the only currency its KHQR.dev store accepts (learned from its error)


def _relay_any(token: str, amount: float, currency: str, bill: str) -> tuple:
    """A KHQR.dev store may accept only KHR (or only USD): then charge the same price in the store's currency."""
    only = _store_currency.get(token)
    if only:
        amount, currency = convert(amount, currency, only)
    try:
        return (*_relay_qr(token, amount, currency, bill), amount, currency)
    except PaymentError as e:
        msg = str(e)
        other = "KHR" if "KHR store" in msg else "USD" if "USD store" in msg else None
        if not other or other == currency:
            raise
        _store_currency[token] = other
        amount, currency = convert(amount, currency, other)
        return (*_relay_qr(token, amount, currency, bill), amount, currency)


def _png(qr: str) -> bytes:
    img = Image.open(io.BytesIO(KHQR().qr_image(qr, "bytes")))
    img = img.resize((img.width * 2, img.height * 2), Image.NEAREST)  # crisper on phones
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def _deeplink(token: str, qr: str, app_name: str):
    try:
        return _relay_call(token, lambda k: k.generate_deeplink(qr, appName=app_name[:30] or "ReplyFlow"), wait_max=0, keep=1)
    except Exception:
        return None


BAKONG_API = "https://api-bakong.nbc.gov.kh/v1"


def _bakong(path: str, token: str, payload) -> dict:
    """Direct Bakong Open API call (the library reports a rejected token as 'UNPAID', which would hide the problem)."""
    import httpx
    try:
        r = httpx.post(f"{BAKONG_API}/{path}", json=payload, headers={"Authorization": f"Bearer {token}"}, timeout=20)
    except httpx.HTTPError as e:
        raise PaymentError(f"Bakong could not be reached ({e.__class__.__name__})")
    try:
        data = r.json()
    except ValueError:
        data = {}
        if r.status_code < 400:
            raise PaymentError(f"Bakong sent an unexpected reply (status {r.status_code})")
    if r.status_code in (401, 403) or data.get("errorCode") == 6:
        raise PaymentError(data.get("responseMessage") or "Bakong rejected the token")
    if r.status_code >= 400:
        raise PaymentError(data.get("responseMessage") or f"Bakong error {r.status_code}")
    return data


def _bulk_paid(token: str, md5s: list) -> list:
    if token.startswith(JWT_PREFIX):
        # one at a time: Bakong's bulk endpoint refuses servers outside Cambodia, the single check answers
        paid = []
        for m in md5s[:50]:
            d = _bakong("check_transaction_by_md5", token, {"md5": m})
            if d.get("responseCode") == 0 and d.get("data"):
                paid.append(m)
        return paid
    try:  # background check: only uses spare budget, never blocks customer QRs
        return _relay_call(token, lambda k: k.check_bulk_payments(md5s[:50]), wait_max=0, keep=_KEEP)
    except ValueError as e:
        if str(e) == BUSY:
            return []  # try again on the next round
        raise PaymentError(str(e))


def _token_ok(token: str) -> tuple:
    try:
        if token.startswith(JWT_PREFIX):
            _bakong("check_transaction_by_md5", token, {"md5": "0" * 32})  # "not found" = token works
        else:
            _relay_call(token, lambda k: k.check_payment("0" * 32), wait_max=10)
        return True, ""
    except (ValueError, PaymentError) as e:
        return False, str(e)


async def make_qr(s, amount: float, currency: str, bill: str) -> dict:
    """Returns {qr, md5, mode, png, deeplink, amount, currency} (amount/currency actually in the QR).
    Uses the relay when the business added a KHQR.dev token."""
    token = (s.khqr_token or "").strip()
    if token.startswith(RELAY_PREFIX):
        qr, md5, amount, currency = await asyncio.to_thread(_relay_any, token, amount, currency, bill)
        mode, link = "relay", await asyncio.to_thread(_deeplink, token, qr, s.business_name)
    else:
        if not ACCOUNT_RE.match(s.bakong_account_id or ""):
            raise PaymentError("Bakong account ID is missing or invalid (example: name@aclb)")
        qr, md5 = await asyncio.to_thread(_local_qr, s.bakong_account_id.strip(), s.bakong_merchant_name or s.business_name,
                                          s.bakong_city or "Phnom Penh", amount, currency, bill)
        # "relay" = checked automatically; a valid Bakong Open API token checks this locally made QR directly with Bakong
        mode, link = ("relay" if jwt_valid(token) else "local"), None
    return {"qr": qr, "md5": md5, "mode": mode, "png": await asyncio.to_thread(_png, qr), "deeplink": link,
            "amount": amount, "currency": currency}


async def qr_png(qr: str) -> bytes:
    return await asyncio.to_thread(_png, qr)


async def bulk_paid(token: str, md5s: list) -> list:
    return await asyncio.to_thread(_bulk_paid, token, md5s)


async def token_ok(token: str) -> tuple:
    return await asyncio.to_thread(_token_ok, token)


def enabled(s) -> bool:
    return (s.khqr_token or "").strip().startswith(RELAY_PREFIX) or bool(ACCOUNT_RE.match(s.bakong_account_id or ""))
    # (a Bakong Open API token needs the account ID too: the QR is made locally, the token only checks payments)


def fmt_amount(amount: float, currency: str) -> str:
    return f"{amount:,.0f}៛" if currency == "KHR" else f"${amount:,.2f}"

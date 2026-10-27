"""Bakong KHQR payments: local QR (manual confirm) or KHQR.dev relay (automatic payment check)."""
import asyncio
import io
import re
import time

from bakong_khqr import KHQR
from PIL import Image

QR_MINUTES = 10
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


def _relay_qr(token: str, amount: float, currency: str, bill: str) -> tuple:
    try:
        res = KHQR(token).create_qr(amount=amount, currency=currency, bill_number=bill)
    except ValueError as e:
        raise PaymentError(str(e))
    return str(res), res.md5


def _png(qr: str) -> bytes:
    img = Image.open(io.BytesIO(KHQR().qr_image(qr, "bytes")))
    img = img.resize((img.width * 2, img.height * 2), Image.NEAREST)  # crisper on phones
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def _deeplink(token: str, qr: str, app_name: str):
    try:
        return KHQR(token).generate_deeplink(qr, appName=app_name[:30] or "ReplyFlow")
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
    try:
        return KHQR(token).check_bulk_payments(md5s[:50])
    except ValueError as e:
        raise PaymentError(str(e))


def _token_ok(token: str) -> tuple:
    try:
        if token.startswith(JWT_PREFIX):
            _bakong("check_transaction_by_md5", token, {"md5": "0" * 32})  # "not found" = token works
        else:
            KHQR(token).check_payment("0" * 32)
        return True, ""
    except (ValueError, PaymentError) as e:
        return False, str(e)


async def make_qr(s, amount: float, currency: str, bill: str) -> dict:
    """Returns {qr, md5, mode, png, deeplink}. Uses the relay when the business added a KHQR.dev token."""
    token = (s.khqr_token or "").strip()
    if token.startswith(RELAY_PREFIX):
        qr, md5 = await asyncio.to_thread(_relay_qr, token, amount, currency, bill)
        mode, link = "relay", await asyncio.to_thread(_deeplink, token, qr, s.business_name)
    else:
        if not ACCOUNT_RE.match(s.bakong_account_id or ""):
            raise PaymentError("Bakong account ID is missing or invalid (example: name@aclb)")
        qr, md5 = await asyncio.to_thread(_local_qr, s.bakong_account_id.strip(), s.bakong_merchant_name or s.business_name,
                                          s.bakong_city or "Phnom Penh", amount, currency, bill)
        # "relay" = checked automatically; a valid Bakong Open API token checks this locally made QR directly with Bakong
        mode, link = ("relay" if jwt_valid(token) else "local"), None
    return {"qr": qr, "md5": md5, "mode": mode, "png": await asyncio.to_thread(_png, qr), "deeplink": link}


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

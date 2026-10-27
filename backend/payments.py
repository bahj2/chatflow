"""Bakong KHQR payments: local QR (manual confirm) or KHQR.dev relay (automatic payment check)."""
import asyncio
import io
import re
import time

from bakong_khqr import KHQR
from PIL import Image

QR_MINUTES = 10
RELAY_PREFIX = "rbk"
ACCOUNT_RE = re.compile(r"^[A-Za-z0-9._-]{2,40}@[A-Za-z0-9._-]{2,20}$")
_NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")


class PaymentError(Exception):
    pass


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


def _bulk_paid(token: str, md5s: list) -> list:
    try:
        return KHQR(token).check_bulk_payments(md5s[:50])
    except ValueError as e:
        raise PaymentError(str(e))


def _token_ok(token: str) -> tuple:
    try:
        KHQR(token).check_payment("0" * 32)
        return True, ""
    except ValueError as e:
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
        mode, link = "local", None
    return {"qr": qr, "md5": md5, "mode": mode, "png": await asyncio.to_thread(_png, qr), "deeplink": link}


async def qr_png(qr: str) -> bytes:
    return await asyncio.to_thread(_png, qr)


async def bulk_paid(token: str, md5s: list) -> list:
    return await asyncio.to_thread(_bulk_paid, token, md5s)


async def token_ok(token: str) -> tuple:
    return await asyncio.to_thread(_token_ok, token)


def enabled(s) -> bool:
    return (s.khqr_token or "").strip().startswith(RELAY_PREFIX) or bool(ACCOUNT_RE.match(s.bakong_account_id or ""))


def fmt_amount(amount: float, currency: str) -> str:
    return f"{amount:,.0f}៛" if currency == "KHR" else f"${amount:,.2f}"

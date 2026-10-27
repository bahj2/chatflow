"""Transactional email through Emergent managed email (Resend). Bodies come only from server-side templates."""
import ipaddress
import logging
import os
import re
from html.parser import HTMLParser
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)

EMAIL_BASE_URL = "https://integrations.emergentagent.com"
EMAIL_KEY = os.environ["EMERGENT_EMAIL_KEY"]
EMAIL_FROM_NAME = os.environ["EMAIL_FROM_NAME"]
EMAIL_REPLY_TO = os.environ.get("EMAIL_REPLY_TO")


class EmailError(Exception):
    pass


_SHORTENERS = ("bit.ly", "tinyurl.com", "t.co", "is.gd", "cutt.ly", "goo.gl", "rebrand.ly")
_CRED_ASK = ("reply with your password", "reply with the code", "send your password", "cvv",
             "send us your password", "enter your password below", "confirm your card number",
             "your full card number", "seed phrase", "recovery phrase", "verify your card",
             "social security number", "confirm your bank details")
_HOSTISH = re.compile(r"\b(?:https?://)?((?:[a-z0-9-]+\.)+[a-z]{2,})", re.I)


def _host_ok(host: str) -> bool:
    if not host or "xn--" in host:
        return False
    try:
        ipaddress.ip_address(host)
        return False
    except ValueError:
        pass
    return not any(host == s or host.endswith("." + s) for s in _SHORTENERS)


def _same_site(shown: str, real: str) -> bool:
    return shown == real or real.endswith("." + shown) or shown.endswith("." + real)


class _EmailScan(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags, self.urls, self.anchors = set(), [], []
        self._href, self._text = None, []

    def handle_starttag(self, tag, attrs):
        self.tags.add(tag.lower())
        self.urls += [v for k, v in attrs if k.lower() in ("href", "src") and v]
        if tag.lower() == "a":
            self._href = dict((k.lower(), v) for k, v in attrs).get("href")
            self._text = []

    def handle_data(self, data):
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "a" and self._href is not None:
            self.anchors.append((self._href, "".join(self._text)))
            self._href, self._text = None, []


def _assert_safe_email(subject: str, html: str) -> None:
    scan = _EmailScan()
    scan.feed(html)
    if scan.tags & {"form", "input", "textarea", "select"}:
        raise ValueError("No forms or input fields in email (G2)")
    body = f"{subject}\n{html}".lower()
    for p in _CRED_ASK:
        if p in body:
            raise ValueError(f"Email asks the recipient for credentials: {p!r} (G2)")
    for url in scan.urls:
        low = url.strip().lower()
        if low.startswith(("mailto:", "tel:", "cid:", "#")):
            continue
        if not low.startswith("https://"):
            raise ValueError(f"Email links/assets must be absolute https: {url!r} (G3)")
        host = urlparse(low).hostname or ""
        if not _host_ok(host) or urlparse(low).username is not None:
            raise ValueError(f"Shortened, numeric-host or credential-bearing URL: {url!r} (G3)")
    for href, text in scan.anchors:
        real = urlparse(href.strip().lower()).hostname or ""
        if not real:
            continue
        for m in _HOSTISH.finditer(text):
            if not _same_site(m.group(1).lower(), real):
                raise ValueError(f"Anchor text {m.group(1)!r} != real link host {real!r} (G3)")


async def send_email(*, to: str, subject: str, html: str) -> str | None:
    _assert_safe_email(subject, html)
    payload = {"to": [to], "subject": subject, "html": html, "from_name": EMAIL_FROM_NAME}
    if EMAIL_REPLY_TO:
        payload["contact_email"] = EMAIL_REPLY_TO
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(f"{EMAIL_BASE_URL}/api/v1/email/send", headers={"X-Email-Key": EMAIL_KEY}, json=payload)
        resp.raise_for_status()
        return resp.json().get("id")
    except httpx.HTTPStatusError as e:
        try:
            body = e.response.json()
        except ValueError:
            body = {}
        if body.get("code") in ("insufficient_credits", "integration_disabled", "daily_limit_reached", "rate_limited"):
            logger.warning(f"Email paused: {body.get('code')} ({e.response.status_code}): {body.get('message', '')}")
            raise EmailError("Email is temporarily unavailable") from e
        logger.error(f"Email send failed: {e.response.status_code} {e.response.text[:300]}")
        raise EmailError("Failed to send email") from e
    except httpx.HTTPError as e:
        logger.error(f"Email send error: {e}")
        raise EmailError("Failed to send email") from e


def reset_code_html(code: str) -> str:
    brand = EMAIL_FROM_NAME
    digits = "".join(f'<td style="padding:0 4px"><div style="width:44px;height:54px;line-height:54px;border-radius:10px;background:#EEF2FF;'
                     f'color:#312E81;font-size:28px;font-weight:700;text-align:center;font-family:Arial,sans-serif">{d}</div></td>' for d in code)
    return (
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#F4F5FB;padding:32px 0">'
        '<tr><td align="center">'
        '<table role="presentation" width="480" cellpadding="0" cellspacing="0" style="max-width:480px;background:#ffffff;border-radius:16px;'
        'border:1px solid #E5E7EB;font-family:Arial,sans-serif;color:#111827">'
        '<tr><td style="padding:28px 32px 8px"><div style="font-size:18px;font-weight:700;color:#4F46E5">' + brand + '</div></td></tr>'
        '<tr><td style="padding:8px 32px 0"><h1 style="margin:0;font-size:22px">Reset your password</h1>'
        '<p style="margin:12px 0 0;font-size:15px;line-height:1.6;color:#4B5563">Use this code on the password reset page to choose a new password.</p></td></tr>'
        '<tr><td align="center" style="padding:24px 32px"><table role="presentation" cellpadding="0" cellspacing="0"><tr>' + digits + '</tr></table></td></tr>'
        '<tr><td style="padding:0 32px 24px"><p style="margin:0;font-size:14px;line-height:1.6;color:#4B5563">The code expires in <strong>15 minutes</strong> and works once. '
        'If you did not request a password reset, you can ignore this email and your password stays the same.</p></td></tr>'
        '<tr><td style="padding:16px 32px 28px;border-top:1px solid #F3F4F6"><p style="margin:0;font-size:12px;line-height:1.6;color:#9CA3AF">'
        'Sent by ' + brand + '. We never ask for your password or payment details by email.</p></td></tr>'
        '</table></td></tr></table>'
    )

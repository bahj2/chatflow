"""Forgot password: a 6-digit code by email (15 minutes, single use, 5 tries), then a new password."""
import asyncio
import hashlib
import hmac
import re
import secrets
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, field_validator

import mailer
from core import db, logger, JWT_SECRET, EMAIL_RE, now_iso, hash_pw, client_ip, rate_ok, member_problem
from routers.auth import issue_token, check_strong

router = APIRouter(prefix="/api")

CODE_TTL = timedelta(minutes=15)
MAX_TRIES = 5
BAD_CODE = "That code is wrong or has expired. Check the email or request a new code."


def _digest(email: str, code: str) -> str:
    return hmac.new(JWT_SECRET.encode(), f"{email}:{code}".encode(), hashlib.sha256).hexdigest()


class ForgotIn(BaseModel):
    email: str = Field(max_length=254)


async def _send_code(email: str, code: str):
    try:
        await mailer.send_email(to=email, subject=f"Your {mailer.EMAIL_FROM_NAME} password reset code: {code}", html=mailer.reset_code_html(code))
    except Exception as e:  # noqa: BLE001 (runs in the background; the request already answered)
        logger.warning(f"reset email to {email} not sent: {e}")


@router.post("/auth/forgot-password")
async def forgot_password(body: ForgotIn, request: Request):
    email = body.email.strip().lower()
    if not re.fullmatch(EMAIL_RE, email):
        raise HTTPException(400, "Please enter a valid email")
    if not await rate_ok([(f"pwreset-ip:{client_ip(request)}", 10, 3600), (f"pwreset:{email}", 1, 60)]):
        raise HTTPException(429, "Please wait a minute before asking for another code.")
    if not await rate_ok([(f"pwreset-h:{email}", 5, 3600)]):
        raise HTTPException(429, "Too many codes requested for this email. Try again in an hour.")
    user = await db.users.find_one({"email": email}, {"_id": 0, "id": 1, "role": 1})
    # Same answer whether or not the account exists; the platform admin's password comes from the server settings
    if user and user.get("role") != "superadmin":
        code = f"{secrets.randbelow(1_000_000):06d}"
        await db.password_resets.delete_many({"email": email})
        await db.password_resets.insert_one({"email": email, "user_id": user["id"], "digest": _digest(email, code), "tries": 0,
                                             "created_at": now_iso(), "exp": datetime.now(timezone.utc) + CODE_TTL})
        asyncio.create_task(_send_code(email, code))
    return {"ok": True}


class ResetIn(BaseModel):
    email: str = Field(max_length=254)
    code: str = Field(min_length=6, max_length=6)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def strong_enough(cls, v: str) -> str:
        return check_strong(v)


@router.post("/auth/reset-password")
async def reset_password(body: ResetIn, request: Request):
    email = body.email.strip().lower()
    if not await rate_ok([(f"pwreset-try:{client_ip(request)}", 30, 3600)]):
        raise HTTPException(429, "Too many tries from this network. Try again later.")
    rec = await db.password_resets.find_one({"email": email})
    if not rec or rec["exp"].replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise HTTPException(400, BAD_CODE)
    if rec["tries"] >= MAX_TRIES:
        await db.password_resets.delete_one({"_id": rec["_id"]})
        raise HTTPException(400, "Too many wrong codes. Please request a new code.")
    if not hmac.compare_digest(rec["digest"], _digest(email, body.code.strip())):
        await db.password_resets.update_one({"_id": rec["_id"]}, {"$inc": {"tries": 1}})
        raise HTTPException(400, BAD_CODE)
    await db.password_resets.delete_many({"email": email})
    user = await db.users.find_one({"id": rec["user_id"], "email": email}, {"_id": 0})
    if not user or user.get("role") == "superadmin":
        raise HTTPException(400, BAD_CODE)
    # The code proves the email is theirs; every older session is signed out
    await db.users.update_one({"id": user["id"]}, {"$set": {"password_hash": hash_pw(body.password), "email_verified": True},
                                                   "$inc": {"token_version": 1}})
    await db.login_attempts.delete_many({"identifier": {"$regex": f":{re.escape(email)}$"}})
    user = await db.users.find_one({"id": user["id"]}, {"_id": 0})
    problem = await member_problem(user)
    if problem:
        raise HTTPException(403, f"Your password is changed, but you can't sign in yet: {problem}")
    return await issue_token(user)

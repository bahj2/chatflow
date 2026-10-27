import re
import uuid
from datetime import datetime, timezone, timedelta

import httpx
import jwt
from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel, Field, field_validator

from core import db, JWT_SECRET, JWT_ALG, EMAIL_RE, Settings, now_iso, hash_pw, verify_pw, current_user, client_ip, rate_ok, member_problem

router = APIRouter(prefix="/api")


class LoginIn(BaseModel):
    email: str
    password: str

@router.post("/auth/login")
async def login(body: LoginIn, request: Request):
    email = body.email.strip().lower()
    ident = f"{client_ip(request)}:{email}"
    att = await db.login_attempts.find_one({"identifier": ident})
    if att and att.get("count", 0) >= 5 and datetime.fromisoformat(att["last"]) > datetime.now(timezone.utc) - timedelta(minutes=15):
        raise HTTPException(429, "Too many attempts. Try again in 15 minutes.")
    user = await db.users.find_one({"email": email})
    if not user or not user.get("password_hash") or not verify_pw(body.password, user["password_hash"]):
        await db.login_attempts.update_one({"identifier": ident}, {"$inc": {"count": 1}, "$set": {"last": now_iso()}}, upsert=True)
        raise HTTPException(401, "Invalid email or password")
    await db.login_attempts.delete_one({"identifier": ident})
    problem = await member_problem(user)
    if problem:
        raise HTTPException(403, problem)
    return await issue_token(user)


async def issue_token(user: dict) -> dict:
    token = jwt.encode({"sub": user["id"], "email": user["email"], "tv": user.get("token_version", 0),
                        "exp": datetime.now(timezone.utc) + timedelta(days=7), "type": "access"}, JWT_SECRET, algorithm=JWT_ALG)
    biz = await db.businesses.find_one({"id": user["business_id"]}, {"_id": 0, "name": 1})
    return {"token": token, "user": {"id": user["id"], "email": user["email"], "name": user.get("name"), "picture": user.get("picture"),
                                     "role": user.get("role"), "business_id": user["business_id"], "business_name": (biz or {}).get("name")}}

async def create_business(name: str, owner_id: str) -> str:
    bid = str(uuid.uuid4())
    await db.businesses.insert_one({"id": bid, "name": name, "owner_id": owner_id, "created_at": now_iso()})
    await db.settings.insert_one({"business_id": bid, **Settings(business_name=name).model_dump()})
    return bid


class RegisterIn(BaseModel):
    email: str
    password: str = Field(min_length=8, max_length=128)
    business_name: str = Field(min_length=1, max_length=80)

    @field_validator("password")
    @classmethod
    def strong_enough(cls, v: str) -> str:
        if not (re.search(r"[A-Za-z]", v) and re.search(r"\d", v)):
            raise ValueError("Password needs at least one letter and one number")
        return v


@router.post("/auth/register")
async def register(body: RegisterIn, request: Request):
    email = body.email.strip().lower()
    if not re.fullmatch(EMAIL_RE, email):
        raise HTTPException(400, "Please enter a valid email")
    if await db.users.find_one({"email": email}):
        raise HTTPException(400, "An account with this email already exists. Please sign in.")
    if not await rate_ok([(f"reg:{client_ip(request)}", 10, 3600)]):
        raise HTTPException(429, "Too many sign-ups from this network. Try again later.")
    uid = str(uuid.uuid4())
    bid = await create_business(body.business_name.strip(), uid)
    user = {"id": uid, "email": email, "name": body.business_name.strip(), "password_hash": hash_pw(body.password),
            "role": "owner", "business_id": bid, "email_verified": False, "created_at": now_iso()}
    await db.users.insert_one(dict(user))
    return await issue_token(user)


class GoogleIn(BaseModel):
    session_id: str


@router.post("/auth/google")
async def google_login(body: GoogleIn):
    try:
        async with httpx.AsyncClient(timeout=20) as h:
            r = await h.get("https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data", headers={"X-Session-ID": body.session_id})
        g = r.json() if r.status_code == 200 else {}
    except (httpx.HTTPError, ValueError):
        raise HTTPException(502, "Google sign-in is unavailable right now. Please try again.")
    if not g.get("email"):
        raise HTTPException(401, "Google sign-in failed. Please try again.")
    user, password_off, _ = await sign_in_verified(g["email"], g.get("name"), g.get("picture"), "google")
    return {**await issue_token(user), "password_off": password_off}


async def sign_in_verified(email: str, name, picture, auth: str):
    """Sign-in where Google/Facebook has proved the email. Returns (user, password_off, created)."""
    email = email.strip().lower()
    user = await db.users.find_one({"email": email}, {"_id": 0})
    password_off = False
    if user:
        problem = await member_problem(user)
        if problem:
            raise HTTPException(403, problem)
        upd = {"$set": {"picture": picture or user.get("picture"), "name": user.get("name") or name, "email_verified": True}}
        if user.get("password_hash") and user.get("email_verified") is False and user.get("role") != "superadmin":
            # The password was set at sign-up without proving the email. Google/Facebook now proves who owns it, so a
            # password someone else may have set is turned off and every older session is signed out.
            upd["$unset"] = {"password_hash": ""}
            upd["$inc"] = {"token_version": 1}
            user["token_version"] = user.get("token_version", 0) + 1
            password_off = True
        await db.users.update_one({"email": email}, upd)
        user["picture"] = picture or user.get("picture")
        return user, password_off, False
    uid = str(uuid.uuid4())
    team = await db.settings.find_one({"allowed_emails": email}, {"_id": 0, "business_id": 1})
    if team:
        bid, role = team["business_id"], "member"
    else:
        bid, role = await create_business(f"{name or email.split('@')[0]}'s business", uid), "owner"
    user = {"id": uid, "email": email, "name": name, "picture": picture, "role": role, "auth": auth,
            "business_id": bid, "email_verified": True, "created_at": now_iso()}
    await db.users.insert_one(dict(user))
    return user, False, True


@router.get("/auth/me")
async def me(user=Depends(current_user)):
    biz = await db.businesses.find_one({"id": user["business_id"]}, {"_id": 0, "name": 1})
    return {**user, "business_name": (biz or {}).get("name")}

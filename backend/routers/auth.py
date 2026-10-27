import re
import uuid
from datetime import datetime, timezone, timedelta

import httpx
import jwt
from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel, Field

from core import db, JWT_SECRET, JWT_ALG, EMAIL_RE, Settings, now_iso, hash_pw, verify_pw, current_user, client_ip, rate_ok

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
    return await issue_token(user)


async def issue_token(user: dict) -> dict:
    token = jwt.encode({"sub": user["id"], "email": user["email"], "exp": datetime.now(timezone.utc) + timedelta(days=7), "type": "access"}, JWT_SECRET, algorithm=JWT_ALG)
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
    password: str = Field(min_length=6, max_length=128)
    business_name: str = Field(min_length=1, max_length=80)


@router.post("/auth/register")
async def register(body: RegisterIn, request: Request):
    email = body.email.strip().lower()
    if not re.fullmatch(EMAIL_RE, email):
        raise HTTPException(400, "Please enter a valid email")
    if not rate_ok([(f"reg:{client_ip(request)}", 10, 3600)]):
        raise HTTPException(429, "Too many sign-ups from this network. Try again later.")
    if await db.users.find_one({"email": email}):
        raise HTTPException(400, "An account with this email already exists. Please sign in.")
    uid = str(uuid.uuid4())
    bid = await create_business(body.business_name.strip(), uid)
    user = {"id": uid, "email": email, "name": body.business_name.strip(), "password_hash": hash_pw(body.password),
            "role": "owner", "business_id": bid, "created_at": now_iso()}
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
    email = g["email"].strip().lower()
    user = await db.users.find_one({"email": email}, {"_id": 0})
    if user:
        await db.users.update_one({"email": email}, {"$set": {"picture": g.get("picture"), "name": user.get("name") or g.get("name")}})
        user["picture"] = g.get("picture")
    else:
        uid = str(uuid.uuid4())
        team = await db.settings.find_one({"allowed_emails": email}, {"_id": 0, "business_id": 1})
        if team:
            bid, role = team["business_id"], "member"
        else:
            bid, role = await create_business(f"{g.get('name') or email.split('@')[0]}'s business", uid), "owner"
        user = {"id": uid, "email": email, "name": g.get("name"), "picture": g.get("picture"), "role": role, "auth": "google",
                "business_id": bid, "created_at": now_iso()}
        await db.users.insert_one(dict(user))
    return await issue_token(user)


@router.get("/auth/me")
async def me(user=Depends(current_user)):
    biz = await db.businesses.find_one({"id": user["business_id"]}, {"_id": 0, "name": 1})
    return {**user, "business_name": (biz or {}).get("name")}

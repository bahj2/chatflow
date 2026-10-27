"""Google sign-in on an account whose password was set without proving the email: password turned off, old sessions ended.
Google's session-data reply is stubbed (MOCKED) - only our own logic is exercised."""
import asyncio, sys, uuid
sys.path.insert(0, '/app/backend')
import httpx
from fastapi import HTTPException
import routers.auth as A
from core import db, current_user

EMAIL = f'victim_{uuid.uuid4().hex[:6]}@gmail.com'


class FakeResp:
    status_code = 200
    def json(self):
        return {'email': EMAIL, 'name': 'Real Owner', 'picture': None}


class FakeClient:
    def __init__(self, *a, **k): pass
    async def __aenter__(self): return self
    async def __aexit__(self, *a): return False
    async def get(self, *a, **k): return FakeResp()


class Req:
    def __init__(self, token): self.headers = {'Authorization': f'Bearer {token}'}


async def main():
    A.httpx.AsyncClient = FakeClient
    class R: headers = {}; client = type('c', (), {'host': '1.2.3.4'})()
    reg = await A.register(A.RegisterIn(email=EMAIL, password='attacker1', business_name='Squat shop'), R())
    old = reg['token']
    g = await A.google_login(A.GoogleIn(session_id='x'))
    print('password_off', g['password_off'])
    u = await db.users.find_one({'email': EMAIL})
    print('password removed', 'password_hash' not in u, '| verified', u['email_verified'], '| tv', u.get('token_version'))
    try:
        await current_user(Req(old)); print('old session STILL valid (bad)')
    except HTTPException as e:
        print('old session rejected', e.status_code)
    print('new session ok', (await current_user(Req(g['token'])))['email'] == EMAIL)
    g2 = await A.google_login(A.GoogleIn(session_id='x'))
    print('second google login password_off', g2['password_off'])
    try:
        await A.login(A.LoginIn(email=EMAIL, password='attacker1'), R()); print('attacker password works (bad)')
    except HTTPException as e:
        print('attacker password rejected', e.status_code)
    bid = u['business_id']
    await db.users.delete_one({'email': EMAIL})
    for c in ('settings', 'subscriptions'):
        await db[c].delete_many({'business_id': bid})
    await db.businesses.delete_one({'id': bid})
    await db.login_attempts.delete_many({'identifier': {'$regex': EMAIL}})

asyncio.run(main())

# Iter23: retest of iter22 fixes - member owner_only on billing checkout / seller voice, register rate-limit order
import os, uuid, bcrypt, pytest, requests
from pymongo import MongoClient

API = open('/app/frontend/.env').read().split('REACT_APP_BACKEND_URL=')[1].split()[0].rstrip('/') + '/api'
DB = MongoClient(os.environ.get('MONGO_URL', 'mongodb://localhost:27017'))['replyflow']
OWNER, MEMBER = 'test_it23owner@example.com', 'test_it23member@example.com'
H = lambda t: {'Authorization': f'Bearer {t}'}


def _cleanup():
    for u in DB.users.find({'email': {'$in': [OWNER]}}):
        for c in ("settings", "conversations", "messages", "subscriptions", "invoices", "ai_usage", "media", "products", "orders"):
            DB[c].delete_many({'business_id': u['business_id']})
        DB.businesses.delete_one({'id': u['business_id']})
        DB.users.delete_many({'business_id': u['business_id']})
    DB.users.delete_many({'email': {'$regex': '^test_it23'}})
    DB.rate_hits.delete_many({})


@pytest.fixture(scope='module')
def ctx():
    _cleanup()
    admin = requests.post(f'{API}/auth/login', json={'email': 'admin@replyflow.com', 'password': 'admin123'}).json()['token']
    r = requests.post(f'{API}/auth/register', json={'email': OWNER, 'password': 'secret123', 'business_name': 'TEST it23'})
    assert r.status_code == 200, r.text
    ot, bid = r.json()['token'], r.json()['user']['business_id']
    assert requests.post(f'{API}/admin/businesses/{bid}/plan', headers=H(admin), json={'plan': 'pro', 'days': 30}).status_code == 200
    s = requests.get(f'{API}/settings', headers=H(ot)).json()
    s.update(allowed_emails=[MEMBER])
    assert requests.put(f'{API}/settings', headers=H(ot), json=s).status_code == 200
    DB.users.insert_one({'id': str(uuid.uuid4()), 'email': MEMBER, 'role': 'member', 'business_id': bid,
                         'password_hash': bcrypt.hashpw(b'member123', bcrypt.gensalt()).decode(), 'created_at': 'x'})
    mr = requests.post(f'{API}/auth/login', json={'email': MEMBER, 'password': 'member123'})
    assert mr.status_code == 200, mr.text
    yield {'owner': ot, 'member': mr.json()['token'], 'admin': admin, 'bid': bid}
    _cleanup()


def test_member_checkout_403(ctx):
    r = requests.post(f'{API}/billing/checkout', headers=H(ctx['member']), json={'item': 'pro'})
    assert r.status_code == 403, r.text


def test_member_topup_checkout_403(ctx):
    r = requests.post(f'{API}/billing/checkout', headers=H(ctx['member']), json={'item': 'topup'})
    assert r.status_code == 403, r.text


def test_owner_checkout_503_or_ok(ctx):
    r = requests.post(f'{API}/billing/checkout', headers=H(ctx['owner']), json={'item': 'pro'})
    print(r.status_code, r.text[:200])
    assert r.status_code in (200, 503), r.text
    if r.status_code == 503:
        assert "isn't set up" in r.json()['detail'] or 'set up' in r.json()['detail']


def test_member_seller_voice_post_403(ctx):
    r = requests.post(f'{API}/settings/seller-voice', headers=H(ctx['member']),
                      files={'file': ('a.wav', b'RIFF0000WAVE', 'audio/wav')}, data={'text': 'hi'})
    assert r.status_code == 403, r.text


def test_member_seller_voice_delete_403(ctx):
    r = requests.delete(f'{API}/settings/seller-voice', headers=H(ctx['member']))
    assert r.status_code == 403, r.text


def test_owner_seller_voice_delete_not_403(ctx):
    r = requests.delete(f'{API}/settings/seller-voice', headers=H(ctx['owner']))
    assert r.status_code != 403, r.text


def test_member_cannot_change_seller_voice_text(ctx):
    s = requests.get(f'{API}/settings', headers=H(ctx['owner'])).json()
    s['seller_voice_text'] = 'owner text'
    assert requests.put(f'{API}/settings', headers=H(ctx['owner']), json=s).status_code == 200
    ms = requests.get(f'{API}/settings', headers=H(ctx['member'])).json()
    ms['seller_voice_text'] = 'HACKED'
    ms['ai_instructions'] = 'member edit ok'
    r = requests.put(f'{API}/settings', headers=H(ctx['member']), json=ms)
    assert r.status_code == 200, r.text
    after = DB.settings.find_one({'business_id': ctx['bid']}) or {}
    assert after.get('seller_voice_text') == 'owner text'


def test_member_billing_status_ok(ctx):
    r = requests.get(f'{API}/billing', headers=H(ctx['member']))
    print(r.status_code, r.text[:200])
    assert r.status_code in (200, 404)


def test_register_duplicate_does_not_consume_limit(ctx):
    DB.rate_hits.delete_many({})
    for _ in range(12):
        r = requests.post(f'{API}/auth/register', json={'email': OWNER, 'password': 'secret123', 'business_name': 'dup'})
        assert r.status_code == 400, r.text
    r = requests.post(f'{API}/auth/register', json={'email': 'test_it23new@example.com', 'password': 'secret123', 'business_name': 'TEST it23 new'})
    assert r.status_code == 200, r.text
    u = DB.users.find_one({'email': 'test_it23new@example.com'})
    if u:
        DB.businesses.delete_one({'id': u['business_id']}); DB.settings.delete_many({'business_id': u['business_id']})
        DB.subscriptions.delete_many({'business_id': u['business_id']})
    DB.rate_hits.delete_many({})

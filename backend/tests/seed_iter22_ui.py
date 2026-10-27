"""Seed for iter22 UI: owner shop (pro) + member. Run with `cleanup` arg to remove."""
import sys, uuid, bcrypt, requests
from pymongo import MongoClient

API = open('/app/frontend/.env').read().split('REACT_APP_BACKEND_URL=')[1].split()[0] + '/api'
DB = MongoClient('mongodb://localhost:27017')['replyflow']
OWNER, MEMBER = 'test_uiowner22@example.com', 'test_uimember22@example.com'
H = lambda t: {'Authorization': f'Bearer {t}'}

if len(sys.argv) > 1 and sys.argv[1] == 'cleanup':
    u = DB.users.find_one({'email': OWNER})
    if u:
        for c in ("settings", "conversations", "messages", "subscriptions", "invoices", "ai_usage", "media", "products", "orders"):
            DB[c].delete_many({'business_id': u['business_id']})
        DB.businesses.delete_one({'id': u['business_id']})
        DB.users.delete_many({'business_id': u['business_id']})
    DB.rate_hits.delete_many({})
    print('cleaned')
    sys.exit()

DB.rate_hits.delete_many({})
admin = requests.post(f'{API}/auth/login', json={'email': 'admin@replyflow.com', 'password': 'admin123'}).json()['token']
own = requests.post(f'{API}/auth/register', json={'email': OWNER, 'password': 'secret123', 'business_name': 'TEST UI Shop 22'}).json()
ot, bid = own['token'], own['user']['business_id']
print(requests.post(f'{API}/admin/businesses/{bid}/plan', headers=H(admin), json={'plan': 'pro', 'days': 30}).status_code)
s = requests.get(f'{API}/settings', headers=H(ot)).json()
s.update(allowed_emails=[MEMBER], bakong_account_id='owner@aclb')
print(requests.put(f'{API}/settings', headers=H(ot), json=s).status_code)
DB.users.insert_one({'id': str(uuid.uuid4()), 'email': MEMBER, 'role': 'member', 'business_id': bid,
                     'password_hash': bcrypt.hashpw(b'member123', bcrypt.gensalt()).decode(), 'created_at': 'x'})
print('seeded', bid)
